"""frameat.py <cast> <HH:MM:SS or +seconds-from-start> <out.png>: copy the frame shown at that wall time."""
import json, sys, time, shutil, datetime
from pathlib import Path
cast, when, out = sys.argv[1], sys.argv[2], sys.argv[3]
fr = json.loads((Path("footage") / cast / "frames.json").read_text()) if (Path("footage") / cast / "frames.json").exists() else None
if fr is None:  # cast still running: list files by mtime
    files = sorted((Path("footage") / cast).glob("*.jpg")); fr = [[f.name, f.stat().st_mtime] for f in files]
if when.startswith("+"):
    t = fr[0][1] + float(when[1:])
else:
    d = datetime.datetime.now().strftime("%Y-%m-%d ") + when
    t = time.mktime(time.strptime(d, "%Y-%m-%d %H:%M:%S"))
best = [f for f in fr if f[1] <= t] or fr[:1]
shutil.copy(Path("footage") / cast / best[-1][0], out); print(best[-1][0], round(best[-1][1] - fr[0][1], 1), "s in")
