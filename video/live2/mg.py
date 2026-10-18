"""Render motion-graphics scenes from motion.html frame by frame (deterministic time, perfect sync).
mg.py <scene> <seconds> <outdir> [beats.json] [--still t1,t2,...]"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
scene, secs, outdir = sys.argv[1], float(sys.argv[2]), Path(sys.argv[3])
beats = json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else {}
stills = [float(x) for x in sys.argv[sys.argv.index("--still") + 1].split(",")] if "--still" in sys.argv else None
outdir.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto("file://" + str((Path(__file__).parent / "motion.html").resolve()))
    pg.evaluate("([s, b]) => window.setup(s, b)", [scene, beats])
    times = stills if stills else [i / 30 for i in range(int(secs * 30))]
    for i, t in enumerate(times):
        pg.evaluate("(t) => window.frame(t)", t)
        pg.screenshot(path=str(outdir / f"{i:05d}.png"))
    b.close()
print(scene, len(times), "frames")
