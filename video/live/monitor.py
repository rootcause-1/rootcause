"""Tee FalkorDB's live command stream (redis-cli MONITOR) to footage/monitor.log with wall-clock timestamps.
Only graph commands are kept; this is the real query traffic RootCause sends, used for the on-screen overlay."""
import subprocess
import time
from pathlib import Path

out = Path(__file__).parent / "footage" / "monitor.log"
out.parent.mkdir(exist_ok=True)
p = subprocess.Popen(["docker", "exec", "rootcause-falkordb-1", "redis-cli", "MONITOR"], stdout=subprocess.PIPE, text=True,
                     bufsize=1)
with open(out, "a") as f:
    for line in p.stdout:
        if "GRAPH." in line:
            f.write(f"{time.time():.3f} {line.strip()}\n")
            f.flush()
