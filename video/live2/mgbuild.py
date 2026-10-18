"""Beats for the motion-graphics scenes, from the voice timing (so each animation step lands on its sentence)."""
import json, subprocess, sys
from pathlib import Path
LEAD, TAIL = 0.35, 0.5
T = json.loads(Path("voice2/timing.json").read_text())
def st(seg):
    s = [LEAD + x for x in T[seg]["starts"]]; d = [b - a for a, b in zip(s, s[1:] + [LEAD + T[seg]["dur"]])]
    return s, d
s, d = st("intro")
beats = {"intro": {"services": s[0] + 0.1, "calls": s[1] + 0.3, "break": s[2] + 0.1, "checkout": s[3] + 0.05,
                   "store": s[3] + 0.6 * d[3], "gateway": s[3] + 0.82 * d[3], "pager": s[4], "real": s[5], "only": s[6], "slow": s[7]}}
s, d = st("pipeline")
keys = ["shop", "coll", "ingest", "db", "gh", "det", "eng", "agent", "act", "ui"]
pb = {"shop": s[0] + 1.0, "coll": s[0] + 0.62 * d[0]}
for k, i in zip(keys[2:], range(1, 9)):
    pb[k] = s[i] + 0.05
beats["pipeline"] = pb
beats["title"], beats["end"] = {}, {}
for scene in sys.argv[1:] or ["intro", "title", "pipeline", "end"]:
    dur = LEAD + T[scene]["dur"] + TAIL
    Path(f"beats_{scene}.json").write_text(json.dumps(beats[scene]))
    subprocess.run(["uv", "run", "--no-project", "--with", "playwright", "python", "mg.py", scene, str(dur), f"mg/{scene}",
                    f"beats_{scene}.json"], check=True)
