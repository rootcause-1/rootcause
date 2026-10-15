"""One-off fix for recordings made before the recorder snapshotted the flag file at start (16 Oct 2026).

Those files begin without a `flag_config` event, so on replay the first flag state seen is already the broken one
and no (:Change) is created. This prepends the flag file as it was when recording started: identical to the first
recorded flag_config except the scenario's flag back at its healthy variant (`off`, or the targeting on-branch for
flags with a targeting rule) — the state the recording harness guarantees before it records.
Usage: uv run python scripts/backfill_flag_snapshot.py replay/paymentFailure.jsonl.gz [...]
"""

import copy
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from rootcause.actions.flagd import with_variant  # noqa: E402
from rootcause.chaos.runner import load_catalogue  # noqa: E402

OFF = {e["flag"]: e.get("off", "off") for e in load_catalogue()}


def main() -> None:
    for path in sys.argv[1:]:
        events = [json.loads(line) for line in gzip.open(path, "rt", encoding="utf-8") if line.strip()]
        start = next(e for e in events if e["type"] == "marker" and e["data"].get("name") == "start")
        flag = start["data"].get("scenario")
        if events[1]["type"] == "flag_config":
            print(f"{path}: already has a snapshot")
            continue
        first = next(e for e in events if e["type"] == "flag_config")
        healthy = with_variant(copy.deepcopy(first["data"]), flag, OFF.get(flag, "off"))
        events.insert(1, {"type": "flag_config", "ts": int(start["ts"]), "data": healthy})
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.writelines(json.dumps(e, separators=(",", ":")) + "\n" for e in events)
        print(f"{path}: prepended healthy flag snapshot ({flag} -> {OFF.get(flag, 'off')})")


if __name__ == "__main__":
    main()
