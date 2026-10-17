"""Build the RootCause demo video end to end: voice-over, explainer scenes, a real run-through, captions, one MP4.

    .venv/Scripts/python video/make_video.py                 # everything
    .venv/Scripts/python video/make_video.py --skip-demo     # reuse the last demo recording (video/build/demo.webm)

Steps
1. Voice-over: every line of video/script.json is spoken by a built-in Windows voice (video/tts.ps1, offline).
2. Explainer scenes: video/scenes.html is recorded at 1920x1080 with Playwright, one scene at a time; each visual
   step starts on the sentence that explains it (the line start times are passed in the URL).
3. Demo: the public replay site is recorded at 1920x1080 while it runs the self-running demo (one click on
   "Start demo"); the time each story stage starts is read from the page. Slow stretches (waiting for alarms to
   clear) are sped up so each narration line lands on its stage; nothing is staged or edited into the app itself.
4. Captions are burned in from the same script; everything is joined into video/out/rootcause-demo.mp4.
Needs: pip install playwright imageio-ffmpeg && playwright install chromium (dev tools, not app dependencies).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
import wave
from pathlib import Path

import imageio_ffmpeg
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
OUT = HERE / "out"
FF = imageio_ffmpeg.get_ffmpeg_exe()
SITE = "http://3.234.90.242/"
W, H, FPS = 1920, 1080, 30
LEAD_S, GAP_S, TAIL_S = 0.8, 0.45, 1.2  # silence before the first line, between lines, after the last line
STAGE_LABELS = {"Healthy": "healthy", "Alerts": "alerts", "One incident": "grouped", "Investigating": "investigating",
                "Root cause": "root", "Impact": "impact", "Fix": "fix", "Fixing": "fixing", "Recovered": "recovered"}


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(cmd[:6])}...\n{r.stderr[-2000:]}")


def wav_len(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


# ---------------------------------------------------------------------------------------------- 1. voice-over
def voice(script: dict) -> dict[str, float]:
    lines = [ln for sc in script["scenes"] for ln in sc["lines"]]
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "narration.json").write_text(json.dumps([{"id": ln["id"], "text": ln["text"]} for ln in lines]), encoding="utf-8")
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "tts.ps1"), "-Script",
         str(BUILD / "narration.json"), "-Out", str(BUILD / "audio"), "-Voice", script["voice"], "-Rate", str(script["rate"])])
    return {ln["id"]: wav_len(BUILD / "audio" / f"{ln['id']}.wav") for ln in lines}


def plan(lines: list[dict], durs: dict[str, float]) -> tuple[list[float], float]:
    """Start time of each line in a scene and the scene length."""
    starts, t = [], LEAD_S
    for ln in lines:
        starts.append(t)
        t += durs[ln["id"]] + GAP_S
    return starts, t - GAP_S + TAIL_S


# ---------------------------------------------------------------------------------------------- 2. explainer scenes
async def record_scene(pw, name: str, starts: list[float], length: float) -> Path:
    browser = await pw.chromium.launch()
    ctx = await browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(BUILD / "raw"),
                                    record_video_size={"width": W, "height": H})
    t0 = time.monotonic()
    page = await ctx.new_page()
    url = (HERE / "scenes.html").as_uri() + f"?s={name}&t=" + ",".join(str(int(s * 1000)) for s in starts)
    await page.goto(url)
    await page.evaluate("document.fonts.ready.then(() => true)")
    lead = time.monotonic() - t0  # recording time before the scene's clock started
    await page.wait_for_timeout(int(length * 1000) + 300)
    video = page.video
    await ctx.close()
    await browser.close()
    raw = Path(await video.path())
    out = BUILD / f"scene_{name}.mp4"
    run([FF, "-y", "-ss", f"{lead:.2f}", "-i", str(raw), "-t", f"{length:.2f}", "-r", str(FPS), "-an",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18", str(out)])
    return out


# ---------------------------------------------------------------------------------------------- 3. demo
async def record_demo(pw) -> tuple[Path, dict[str, float]]:
    browser = await pw.chromium.launch()
    ctx = await browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(BUILD / "raw"),
                                    record_video_size={"width": W, "height": H})
    t0 = time.monotonic()
    page = await ctx.new_page()
    await page.goto(SITE)
    await page.wait_for_selector("text=Start demo", timeout=30_000)
    await page.wait_for_timeout(1500)
    await page.get_by_role("button", name="Start demo").first.click()
    # the page may still show a previous visitor's run until the restart lands: only log stages from "healthy" on
    started = False
    stages: dict[str, float] = {}
    deadline = time.monotonic() + 480
    while time.monotonic() < deadline:
        label = await page.evaluate("""() => { const el = [...document.querySelectorAll('header li span')]
            .find(s => s.className.includes('bg-eucalyptus')); return el ? el.innerText.replace(/^\\d+\\s*/, '').trim() : null; }""")
        st = STAGE_LABELS.get(label or "")
        started = started or st == "healthy"
        if started and st and st not in stages:
            stages[st] = time.monotonic() - t0
            print(f"  demo stage {st:14} at {stages[st]:6.1f}s", flush=True)
        if "recovered" in stages and time.monotonic() - t0 > stages["recovered"] + 9:
            break
        await page.wait_for_timeout(250)
    video = page.video
    await ctx.close()
    await browser.close()
    if "recovered" not in stages:
        raise SystemExit(f"the demo never reached 'recovered' (stages seen: {stages}); not building a video without its ending")
    raw = Path(await video.path())
    dst = BUILD / "demo.webm"
    dst.write_bytes(raw.read_bytes())
    (BUILD / "demo_stages.json").write_text(json.dumps(stages, indent=1))
    return dst, stages


def edit_demo(src: Path, stages: dict[str, float], lines: list[dict], durs: dict[str, float]) -> tuple[Path, list[float], float]:
    """One block per narration line (from its stage to the next line's stage). A block longer than its line is sped
    up (at most 6x); a shorter one holds its last frame. Returns the edited clip, line starts and length."""
    present = [ln for ln in lines if ln["stage"] in stages]
    end = stages.get("recovered", max(stages.values())) + 9
    parts, starts, t = [], [], 0.0
    for i, ln in enumerate(present):
        a = stages[ln["stage"]]
        b = stages[present[i + 1]["stage"]] if i + 1 < len(present) else end
        need = durs[ln["id"]] + 0.9
        raw_len = max(0.5, b - a)
        speed = min(6.0, max(1.0, raw_len / need))
        out_len = max(need, raw_len / speed)
        seg = BUILD / f"demo_{i:02d}.mp4"
        hold = max(0.0, out_len - raw_len / speed)
        vf = f"setpts=PTS/{speed:.3f},fps={FPS}" + (f",tpad=stop_mode=clone:stop_duration={hold:.2f}" if hold > 0.05 else "")
        run([FF, "-y", "-ss", f"{a:.2f}", "-t", f"{raw_len:.2f}", "-i", str(src), "-vf", vf, "-an",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18", str(seg)])
        parts.append(seg)
        starts.append(t + 0.3)
        t += out_len
        print(f"  block {ln['stage']:13} raw {raw_len:5.1f}s  x{speed:.2f}  -> {out_len:5.1f}s", flush=True)
    lst = BUILD / "demo_parts.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    out = BUILD / "scene_demo.mp4"
    run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return out, starts, t


# ---------------------------------------------------------------------------------------------- 4. audio, captions, final
def with_audio(video: Path, lines: list[dict], starts: list[float], length: float) -> Path:
    out = video.with_name(video.stem + "_av.mp4")
    cmd = [FF, "-y", "-i", str(video)]
    for ln in lines:
        cmd += ["-i", str(BUILD / "audio" / f"{ln['id']}.wav")]
    chains = [f"[{i + 1}:a]aresample=48000,adelay={int(s * 1000)}:all=1[a{i}]" for i, s in enumerate(starts)]
    mix = "".join(f"[a{i}]" for i in range(len(lines)))
    fc = ";".join(chains) + f";{mix}amix=inputs={len(lines)}:normalize=0,apad[aout]"
    cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-t", f"{length:.2f}", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)]
    run(cmd)
    return out


def ass_time(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def captions(cues: list[tuple[float, float, str]]) -> Path:
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Segoe UI,40,&H00FFFFFF,&H00FFFFFF,&H00262A1E,&H96262A1E,0,0,0,0,100,100,0,0,3,14,0,2,260,260,46,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = "".join(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Cap,,0,0,0,,{txt}\n" for a, b, txt in cues)
    p = BUILD / "captions.ass"
    p.write_text(head + body, encoding="utf-8")
    return p


async def main(skip_demo: bool, only: set[str] | None = None) -> None:
    script = json.loads((HERE / "script.json").read_text(encoding="utf-8"))
    print("1/4 voice-over", flush=True)
    durs = voice(script)
    clips, cues, clock = [], [], 0.0
    async with async_playwright() as pw:
        for sc in script["scenes"]:
            name, lines = sc["scene"], sc["lines"]
            if only and name not in only:
                continue
            if name == "demo":
                print("3/4 demo run-through", flush=True)
                src = BUILD / "demo.webm"
                if skip_demo and src.exists():
                    stages = json.loads((BUILD / "demo_stages.json").read_text())
                else:
                    src, stages = await record_demo(pw)
                video, starts, length = edit_demo(src, stages, lines, durs)
                lines = [ln for ln in lines if ln["stage"] in stages]
            else:
                print(f"2/4 scene {name}", flush=True)
                starts, length = plan(lines, durs)
                video = await record_scene(pw, name, starts, length)
            clips.append(with_audio(video, lines, starts, length))
            cues += [(clock + s, clock + s + durs[ln["id"]] + 0.2, ln["text"]) for ln, s in zip(lines, starts, strict=True)]
            clock += length
    print("4/4 captions and final cut", flush=True)
    lst = BUILD / "parts.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in clips))
    joined = BUILD / "joined.mp4"
    run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    ass = captions(cues)
    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / ("rootcause-demo.mp4" if not only else f"preview-{'-'.join(sorted(only))}.mp4")
    ass_arg = ass.as_posix().replace(":", "\\:")
    run([FF, "-y", "-i", str(joined), "-vf", f"ass='{ass_arg}'", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
         "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", str(final)])
    (OUT / "rootcause-demo.srt").write_text("".join(
        f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n\n" for i, (a, b, txt) in enumerate(cues, 1)),
        encoding="utf-8")
    print(f"done: {final} ({clock:.0f} s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-demo", action="store_true", help="reuse video/build/demo.webm and its stage times")
    ap.add_argument("--only", help="comma-separated scenes to render into a preview (e.g. cold,graph)")
    a = ap.parse_args()
    asyncio.run(main(a.skip_demo, set(a.only.split(",")) if a.only else None))
