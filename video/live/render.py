"""Cut the recorded footage into the 3:00 demo video.

Each scene = one voice line (voice/<key>.wav) + clips of real recordings (footage/<cast>/frames.json, wall-clock
timestamps). A clip maps output time to source time linearly (so a long wait becomes a sped-up shot, labelled
with its speed). Zoom = a crop rectangle in source pixels, eased between keyframes. Overlays: captions, speed badge,
the live FalkorDB query stream (footage/monitor.log, real MONITOR output), picture-in-picture of another cast.
Output: out/scenes/<key>.mp4 and out/rootcause-demo.mp4 (1920x1080, 30 fps, H.264 + AAC)."""
import bisect
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
FOOT, VOICE, OUT = HERE / "footage", HERE / "voice", HERE / "out"
(OUT / "scenes").mkdir(parents=True, exist_ok=True)
W, H, FPS = 1920, 1080, 30
LEAD, TAIL = 0.35, 0.55

F_SANS = "/System/Library/Fonts/SFNS.ttf"
F_SERIF = "/System/Library/Fonts/Supplemental/Georgia.ttf"
F_MONO = "/System/Library/Fonts/Menlo.ttc"
PINE, PAPER, GREEN, RED, AMBER, PLUM = (30, 38, 33), (251, 250, 245), (31, 92, 69), (210, 81, 63), (217, 142, 47), (124, 102, 199)


def font(path, size):
    return ImageFont.truetype(path, size)


# ---------------------------------------------------------------- data
EVENTS = [json.loads(line) for line in (FOOT / "events.jsonl").read_text().splitlines() if line.strip()]


def ev(name, i=0):
    hits = [e for e in EVENTS if e["event"] == name]
    if not hits:
        raise KeyError(name)
    return hits[i]


def t_of(name, i=0):
    return ev(name, i)["t"]


class Cast:
    cache = {}

    def __init__(self, name):
        self.name = name
        self.frames = json.loads((FOOT / name / "frames.json").read_text())
        self.ts = [f[1] for f in self.frames]

    @property
    def t0(self):
        return self.ts[0]

    @property
    def t1(self):
        return self.ts[-1]

    def at(self, t):
        i = max(0, bisect.bisect_right(self.ts, t) - 1)
        fn = self.frames[i][0]
        key = (self.name, fn)
        if key not in Cast.cache:
            if len(Cast.cache) > 400:
                Cast.cache.clear()
            Cast.cache[key] = Image.open(FOOT / self.name / fn).convert("RGB")
        return Cast.cache[key]


CASTS = {}


def cast(name):
    if name not in CASTS:
        CASTS[name] = Cast(name)
    return CASTS[name]


MONITOR = []
if (FOOT / "monitor.log").exists():
    for line in (FOOT / "monitor.log").read_text(errors="ignore").splitlines():
        try:
            ts, rest = line.split(" ", 1)
            MONITOR.append((float(ts), rest))
        except ValueError:
            pass
MON_TS = [m[0] for m in MONITOR]


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def lerp_rect(keys, frac):
    """keys: [(frac, (x, y, w)), ...] ; h follows 16:9."""
    if not keys:
        return (0, 0, W)
    if frac <= keys[0][0]:
        return keys[0][1]
    for (f0, r0), (f1, r1) in zip(keys, keys[1:]):
        if f0 <= frac <= f1:
            k = ease((frac - f0) / max(1e-6, f1 - f0))
            return tuple(a + (b - a) * k for a, b in zip(r0, r1))
    return keys[-1][1]


# ---------------------------------------------------------------- overlays
def rounded(draw, box, r, fill, outline=None, width=1):
    draw.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def caption(img, text, sub=None, pos="bl"):
    d = ImageDraw.Draw(img, "RGBA")
    f1, f2 = font(F_SANS, 34), font(F_SANS, 24)
    w1 = d.textlength(text, font=f1)
    w2 = d.textlength(sub, font=f2) if sub else 0
    bw, bh = int(max(w1, w2) + 56), (98 if sub else 66)
    x = 48 if pos == "bl" else W - bw - 48
    y = H - bh - 44
    rounded(d, (x, y, x + bw, y + bh), 16, (30, 38, 33, 228))
    d.text((x + 28, y + 14), text, font=f1, fill=PAPER)
    if sub:
        d.text((x + 28, y + 58), sub, font=f2, fill=(200, 205, 196))


def badge(img, text, color=PLUM):
    d = ImageDraw.Draw(img, "RGBA")
    f = font(F_SANS, 30)
    w = d.textlength(text, font=f)
    rounded(d, (W - w - 96, 36, W - 40, 92), 28, color + (235,))
    d.text((W - w - 68, 46), text, font=f, fill=(255, 255, 255))


def live_tag(img):
    d = ImageDraw.Draw(img, "RGBA")
    f = font(F_SANS, 24)
    rounded(d, (40, 36, 236, 84), 24, (210, 81, 63, 235))
    d.ellipse((60, 52, 76, 68), fill=(255, 255, 255))
    d.text((88, 45), "LIVE RUN", font=f, fill=(255, 255, 255))


def monitor_panel(img, t, box=(48, 560, 900, 1000), title="FalkorDB · live queries (redis MONITOR)"):
    i = bisect.bisect_right(MON_TS, t)
    lines = MONITOR[max(0, i - 11):i]
    d = ImageDraw.Draw(img, "RGBA")
    x0, y0, x1, y1 = box
    rounded(d, box, 16, (18, 22, 20, 236))
    d.text((x0 + 22, y0 + 14), title, font=font(F_SANS, 22), fill=(170, 220, 190))
    j = bisect.bisect_left(MON_TS, t - 10)
    recent = [m[1] for m in MONITOR[j:i]]
    counts = [(k, sum(k in r for r in recent)) for k in ("algo.WCC", "algo.pageRank", "shortestPath", "algo.bfs")]
    summary = "last 10 s: " + "  ·  ".join(f"{n}× {k}" for k, n in counts if n) if any(n for _, n in counts) else ""
    d.text((x0 + 22, y0 + 44), summary, font=font(F_MONO, 18), fill=(255, 190, 120))
    fm = font(F_MONO, 17)
    y = y0 + 80
    for ts, raw in lines:
        q = raw.split('"GRAPH.', 1)[-1]
        q = "GRAPH." + q.replace('\\"', '"').replace("\\n", " ")
        q = " ".join(q.split())
        hot = any(k in q for k in ("algo.WCC", "algo.pageRank", "shortestPath", "algo.bfs", "BLAMES", "algo.betweenness"))
        col = (255, 190, 120) if hot else (205, 210, 200)
        d.text((x0 + 22, y), q[: int((x1 - x0 - 44) / 10.3)], font=fm, fill=col)
        y += 32
        if y > y1 - 30:
            break


def pip(img, src, t, box):
    x0, y0, x1, y1 = box
    fr = cast(src).at(t).resize((x1 - x0, y1 - y0), Image.LANCZOS)
    d = ImageDraw.Draw(img, "RGBA")
    rounded(d, (x0 - 6, y0 - 6, x1 + 6, y1 + 6), 14, (30, 38, 33, 230))
    img.paste(fr, (x0, y0))


def title_card(img, title, sub, dim=170):
    base = img.filter(ImageFilter.GaussianBlur(6))
    ov = Image.new("RGBA", (W, H), (30, 38, 33, dim))
    base = Image.alpha_composite(base.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(base)
    ft, fs = font(F_SERIF, 132), font(F_SANS, 40)
    tw = d.textlength(title, font=ft)
    d.text(((W - tw) / 2, 380), title, font=ft, fill=PAPER)
    for k, line in enumerate(sub.split("\n")):
        sw = d.textlength(line, font=fs)
        d.text(((W - sw) / 2, 560 + k * 58), line, font=fs, fill=(214, 220, 210))
    return base


def text_frame(lines, bg=PAPER):
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    y = 300
    for size, txt, col, fp in lines:
        f = font(fp, size)
        for part in textwrap.wrap(txt, width=int(1500 / (size * 0.5))) or [""]:
            tw = d.textlength(part, font=f)
            d.text(((W - tw) / 2, y), part, font=f, fill=col)
            y += int(size * 1.35)
        y += 18
    return img


# ---------------------------------------------------------------- clip rendering
def render_clip(clip, out_dur, push):
    n = max(1, round(out_dur * FPS))
    kind = clip.get("kind", "cast")
    if kind == "still":
        still = clip["image"]
    else:
        src = cast(clip["cast"])
        t0, t1 = clip["t0"], clip["t1"]
        speed = (t1 - t0) / out_dur
    for k in range(n):
        frac = k / max(1, n - 1)
        if kind == "still":
            img = still.copy()
            t = None
        else:
            t = t0 + (k / FPS) * speed
            img = src.at(t)
            x, y, w = lerp_rect(clip.get("zoom", []), frac)
            if w < W - 1:
                h = w * H / W
                img = img.crop((int(x), int(y), int(x + w), int(y + h))).resize((W, H), Image.LANCZOS)
            else:
                img = img.copy()
        for ov in clip.get("overlays", []):
            a, b = ov.get("from", 0), ov.get("to", 1)
            if not (a <= frac <= b):
                continue
            typ = ov["type"]
            if typ == "caption":
                caption(img, ov["text"], ov.get("sub"), ov.get("pos", "bl"))
            elif typ == "badge":
                badge(img, ov["text"], ov.get("color", PLUM))
            elif typ == "speed" and t is not None and speed > 1.4:
                badge(img, f"{speed:.0f}× speed")
            elif typ == "live":
                live_tag(img)
            elif typ == "monitor" and t is not None:
                monitor_panel(img, t, ov.get("box", (48, 560, 900, 1000)))
            elif typ == "pip" and t is not None:
                pip(img, ov["cast"], t + ov.get("offset", 0), ov["box"])
            elif typ == "title":
                img = title_card(img, ov["text"], ov["sub"])
        push(img)


def render_scene(scene):
    key = scene["key"]
    vdur = json.loads((VOICE / "durations.json").read_text()).get(key, 0) if scene.get("voice", True) else 0
    dur = scene.get("dur") or (LEAD + vdur + TAIL)
    clips = scene["clips"]
    fixed = sum(c.get("dur", 0) for c in clips)
    flex = [c for c in clips if "dur" not in c]
    each = max(0.5, (dur - fixed) / len(flex)) if flex else 0
    out = OUT / "scenes" / f"{key}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-"]
    if vdur:
        cmd += ["-i", str(VOICE / f"{key}.wav"), "-filter_complex",
                f"[1:a]adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad[a]", "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-ar", "48000", "-ac", "2", "-shortest", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    count = [0]

    def push(img):
        p.stdin.write(img.tobytes())
        count[0] += 1

    for c in clips:
        render_clip(c, c.get("dur", each), push)
    p.stdin.close()
    p.wait()
    print(f"{key}: {count[0] / FPS:.1f}s video, voice {vdur:.1f}s -> {out.name}", flush=True)
    return out


def concat(paths, out):
    lst = OUT / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in paths))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)],
                   check=True)
    d = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)])
    print("final", out, round(float(d), 1), "s")


if __name__ == "__main__":
    from scenes import SCENES
    only = set(sys.argv[1:])
    paths = []
    for sc in SCENES:
        path = OUT / "scenes" / f"{sc['key']}.mp4"
        if not only or sc["key"] in only:
            render_scene(sc)
        paths.append(path)
    if not only:
        concat(paths, OUT / "rootcause-demo.mp4")
