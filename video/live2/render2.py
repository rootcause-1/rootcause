"""Compose the demo video: motion-graphics scenes (motion.html, rendered frame by frame) and the master live take
(footage2/, full pages at native 1770x996, never zoomed or rescaled) on one stage, with a step tracker on top that
follows the app's own step bar (footage2/steps.jsonl), honest speed badges, captions, short crossfades, and the
Kokoro narration placed sentence by sentence (voice2/). Output out2/rootcause-demo.mp4 (1920x1080, 30 fps)."""
import bisect
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
FOOT, VOICE, OUT, MG = HERE / "footage3", HERE / "voice2", HERE / "out2", HERE / "mg"
OUT.mkdir(exist_ok=True)
W, H, FPS = 1920, 1080, 30
FX, FY, FW, FH = 76, 84, 1768, 996          # footage window on the stage (= the capture size, pasted 1:1)
LEAD, TAIL, XFADE = 0.18, 0.30, 8

F_SANS = "/System/Library/Fonts/SFNS.ttf"
F_MONO = "/System/Library/Fonts/Menlo.ttc"
F_SERIF = "/System/Library/Fonts/Supplemental/Georgia.ttf"
PINE, PAPER, STAGE, GREEN, RED, PLUM, MIST, SOFT = (30, 38, 33), (251, 250, 245), (236, 232, 221), (31, 92, 69), (210, 81, 63), (124, 102, 199), (226, 222, 208), (110, 114, 106)
STEPS = ["Healthy", "Alerts", "One incident", "Investigating", "Root cause", "Impact", "Fix", "Fixing", "Recovered",
         "Pull request", "Merged"]
_fonts = {}


def font(path, size):
    if (path, size) not in _fonts:
        _fonts[(path, size)] = ImageFont.truetype(path, size)
    return _fonts[(path, size)]


EVENTS = [json.loads(x) for x in (FOOT / "events.jsonl").read_text().splitlines() if x.strip()]
STEPLOG = [json.loads(x) for x in (FOOT / "steps.jsonl").read_text().splitlines() if x.strip()]
STEP_TS = [s["t"] for s in STEPLOG]
TIMING = json.loads((VOICE / "timing.json").read_text())


def ev(name, **match):
    hits = [e for e in EVENTS if e["event"] == name and all(e.get(k) == v for k, v in match.items())]
    return hits[-1]["t"] if hits else None


class Cast:
    def __init__(self, name):
        self.name = name
        self.frames = json.loads((FOOT / name / "frames.json").read_text())
        self.ts = [f[1] for f in self.frames]
        self.cache = (None, None)

    def at(self, t):
        i = max(0, bisect.bisect_right(self.ts, t) - 1)
        fn = self.frames[i][0]
        if self.cache[0] != fn:
            im = Image.open(FOOT / self.name / fn).convert("RGB")
            if im.size != (FW, FH):
                im = im.resize((FW, FH), Image.LANCZOS)
            self.cache = (fn, im)
        return self.cache[1]


CASTS = {}


def cast(name):
    if name not in CASTS:
        CASTS[name] = Cast(name)
    return CASTS[name]


def tracker_state(t):
    """(active step, done steps) at wall time t, from the app's own step bar plus the PR / merge events."""
    i = bisect.bisect_right(STEP_TS, t) - 1
    active, done = ("Healthy", [])
    if i >= 0:
        s = STEPLOG[i]
        active, done = s["active"] or (s["done"][-1] if s["done"] else "Healthy"), list(s["done"])
    pr, merged = ev("pr_open"), ev("merged_seen")
    if pr and t >= pr:
        done, active = STEPS[:9], "Pull request"
    if merged and t >= merged:
        done, active = STEPS[:10], "Merged"
    return active, set(done)


# ---------------------------------------------------------------- drawing
def stage(foot, t_wall, chapter, badge, caption=None, sub=None):
    img = Image.new("RGB", (W, H), STAGE)
    d = ImageDraw.Draw(img, "RGBA")
    # header: brand + chapter, then the tracker
    d.ellipse((34, 32, 50, 48), fill=RED)
    d.text((60, 22), "RootCause", font=font(F_SERIF, 30), fill=PINE)
    d.text((222, 30), chapter, font=font(F_SANS, 20), fill=SOFT)
    active, done = tracker_state(t_wall) if t_wall else ("Healthy", set())
    f = font(F_SANS, 18)
    widths = [int(d.textlength(s, font=f)) + 30 for s in STEPS]
    gap = 6
    x = W - 30 - (sum(widths) + gap * (len(STEPS) - 1))
    for s, w in zip(STEPS, widths):
        box = (x, 22, x + w, 62)
        if s == active:
            d.rounded_rectangle(box, 20, fill=GREEN)
            d.text((x + 15, 31), s, font=f, fill=(255, 255, 255))
        elif s in done:
            d.rounded_rectangle(box, 20, fill=(222, 233, 225), outline=(190, 208, 196))
            d.text((x + 15, 31), s, font=f, fill=GREEN)
        else:
            d.rounded_rectangle(box, 20, outline=MIST, width=2)
            d.text((x + 15, 31), s, font=f, fill=(150, 152, 145))
        x += w + gap
    # footage, native pixels
    d.rounded_rectangle((FX - 2, FY - 2, FX + FW + 2, FY + FH + 2), 6, fill=(205, 200, 186))
    img.paste(foot, (FX, FY))
    d = ImageDraw.Draw(img, "RGBA")
    if badge:
        fb = font(F_SANS, 22)
        bw = int(d.textlength(badge, font=fb)) + 44
        x0 = FX + FW - bw - 18
        col = (210, 81, 63, 235) if "real time" in badge else (124, 102, 199, 235)
        d.rounded_rectangle((x0, FY + FH - 62, x0 + bw, FY + FH - 18), 22, fill=col)
        d.ellipse((x0 + 16, FY + FH - 46, x0 + 28, FY + FH - 34), fill=(255, 255, 255))
        d.text((x0 + 34, FY + FH - 53), badge, font=fb, fill=(255, 255, 255))
    if caption:
        f1, f2 = font(F_SANS, 30), font(F_SANS, 22)
        w1 = d.textlength(caption, font=f1)
        w2 = d.textlength(sub, font=f2) if sub else 0
        bw, bh = int(max(w1, w2) + 48), (92 if sub else 60)
        x0, y0 = FX + 20, FY + FH - bh - 18
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 14, fill=(30, 38, 33, 232))
        d.text((x0 + 24, y0 + 12), caption, font=f1, fill=PAPER)
        if sub:
            d.text((x0 + 24, y0 + 54), sub, font=f2, fill=(205, 212, 200))
    return img


# ---------------------------------------------------------------- segments
def seg_duration(seg):
    vd = TIMING[seg["key"]]["dur"]
    return max(seg.get("min_dur", 0), LEAD + vd + TAIL)


def clip_bounds(seg, dur):
    """Clip i starts at sentence clip['at'] (or at clip['frac'] of the segment); otherwise right after the previous one."""
    starts = TIMING[seg["key"]]["starts"]
    bounds = []
    for i, c in enumerate(seg["clips"]):
        if i == 0:
            bounds.append(0.0)
        elif "at" in c and not seg.get("spread"):
            bounds.append(LEAD + starts[c["at"]])
        elif "frac" in c:
            bounds.append(dur * c["frac"])
        else:
            bounds.append(None)
    for i in range(len(bounds)):
        if bounds[i] is None:
            bounds[i] = bounds[i - 1] + (dur - bounds[i - 1]) / (len(bounds) - i + 1)
    bounds.append(dur)
    return [(bounds[i], bounds[i + 1]) for i in range(len(seg["clips"]))]


def render(segments, out_name="rootcause-demo.mp4", only=None):
    total = sum(seg_duration(s) for s in segments)
    audio = np.zeros((int((total + 1) * 48000), 2), dtype=np.float32)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", "-tune", "stillimage",
           str(OUT / "video_only.mp4")]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t_out, prev, n_frames = 0.0, None, 0
    for seg in segments:
        dur = seg_duration(seg)
        a, sr = sf.read(VOICE / f"{seg['key']}.wav", dtype="float32")
        if seg.get("spread"):
            st = TIMING[seg["key"]]["starts"] + [TIMING[seg["key"]]["dur"]]
            spans = clip_bounds(seg, dur)
            for c, (b0, _b1) in zip(seg["clips"], spans):
                pos = t_out + b0 + LEAD
                for j in c.get("say", []):
                    piece = a[int(st[j] * sr): int(st[j + 1] * sr)]
                    i0 = int(pos * sr)
                    audio[i0:i0 + len(piece)] += piece[: max(0, len(audio) - i0)]
                    pos += len(piece) / sr
        else:
            i0 = int((t_out + LEAD) * sr)
            audio[i0:i0 + len(a)] += a[: max(0, len(audio) - i0)]
        n = int(round(dur * FPS))
        if seg["kind"] == "mg":
            frames = sorted((MG / seg["key"]).glob("*.png"))
            get = lambda k, fr=frames: Image.open(fr[min(k, len(fr) - 1)]).convert("RGB")
        else:
            spans = clip_bounds(seg, dur)

            def get(k, seg=seg, spans=spans):
                tt = k / FPS
                ci = next((i for i, (a0, a1) in enumerate(spans) if a0 <= tt < a1), len(spans) - 1)
                c, (a0, a1) = seg["clips"][ci], spans[ci]
                src = cast(c["cast"])
                speed = c.get("speed") or (max(1.0, (c["t1"] - c["t0"]) / max(0.1, a1 - a0)) if "t1" in c else 1.0)
                tw = c["t0"] + (tt - a0) * speed
                badge = "LIVE · real time" if speed < 1.25 else f"LIVE · {speed:.1f}× speed".replace(".0×", "×")
                cap, sub_ = c.get("caption"), c.get("sub")
                if c.get("caption_after") and tw < c["caption_after"]:
                    cap, sub_ = c.get("pre_caption"), None
                return stage(src.at(tw), tw, seg.get("chapter", "Live demo"), badge, cap, sub_)
        for k in range(n):
            img = get(k)
            if prev is not None and k < XFADE:
                img = Image.blend(prev, img, (k + 1) / (XFADE + 1))
            p.stdin.write(img.tobytes())
            n_frames += 1
        prev = img
        t_out += n / FPS
        print(f"{seg['key']:12s} {dur:5.1f}s  -> {t_out:6.1f}s", flush=True)
    p.stdin.close()
    p.wait()
    audio = audio[: int(t_out * 48000)]
    sf.write(OUT / "voice_track.wav", audio, 48000)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(OUT / "video_only.mp4"), "-i", str(OUT / "voice_track.wav"),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(OUT / out_name)], check=True)
    print("final", OUT / out_name, round(t_out, 1), "s")


if __name__ == "__main__":
    from edit2 import SEGMENTS
    keys = set(sys.argv[1:])
    render([s for s in SEGMENTS if not keys or s["key"] in keys], "preview.mp4" if keys else "rootcause-demo.mp4")
