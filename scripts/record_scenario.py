"""Record one replay scenario through the running API (live mode):
3 min healthy -> flip the flag (marker `break`) -> 3 min broken -> revert (marker `fix`) -> 2 min recovery.

Usage: python scripts/record_scenario.py --scenario paymentFailure [--api http://localhost:8000]
The scenario name is the catalogue flag; its variant comes from backend/rootcause/chaos/catalogue.yaml.
The recorded `fix` marker is {kind: flag_revert, target: <flag>}: the replay player recovers when the agent's
approved action matches it.
"""

import argparse
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from rootcause.actions.flagd import set_variant  # noqa: E402
from rootcause.chaos.runner import load_catalogue  # noqa: E402
from rootcause.settings import get_settings  # noqa: E402


def wait(seconds: int, label: str) -> None:
    for left in range(seconds, 0, -15):
        print(f"  {label}: {left}s left")
        time.sleep(min(15, left))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--healthy", type=int, default=180)
    ap.add_argument("--broken", type=int, default=180)
    ap.add_argument("--recovery", type=int, default=120)
    args = ap.parse_args()
    entry = next((e for e in load_catalogue() if e["flag"] == args.scenario), None)
    if not entry:
        sys.exit(f"{args.scenario} is not in the chaos catalogue")
    path = get_settings().flagd_path
    if not path:
        sys.exit("set FLAGD_CONFIG_PATH (host path to demo.flagd.json)")

    api = httpx.Client(base_url=args.api, timeout=30)
    print(api.post("/api/record/start", json={"scenario": args.scenario}).json())
    wait(args.healthy, "healthy")
    set_variant(path, entry["flag"], entry["variant"], actor="harness")
    api.post("/api/record/marker", json={"name": "break", "data": {"flag": entry["flag"]}})
    wait(args.broken, "broken")
    api.post("/api/record/marker", json={"name": "fix", "data": {"kind": "flag_revert", "target": entry["flag"]}})
    set_variant(path, entry["flag"], entry.get("off", "off"), actor="harness")
    wait(args.recovery, "recovery")
    print(api.post("/api/record/stop").json())


if __name__ == "__main__":
    main()
