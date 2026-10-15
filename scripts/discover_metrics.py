"""List Prometheus metric names and print candidates for config/rootcause.yaml (prometheus.queries).

Usage: python scripts/discover_metrics.py [--url http://localhost:9090]
It only *suggests*: a human checks the candidates and writes the real PromQL into the config (never guessed).
"""

import argparse
import re

import httpx

PATTERNS = {
    "kafka_lag": r"(consumer.*lag|lag.*consumer|kafka.*lag)",
    "span_metrics_calls": r"(traces_span_metrics_calls|calls_total|span.*calls)",
    "span_metrics_duration": r"(traces_span_metrics_duration|duration.*bucket)",
    "runtime_memory": r"(process_memory|process_runtime.*memory|jvm_memory_used|runtime.*heap|memory_usage)",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:9090", help="Prometheus base URL (via a port-forward or proxy)")
    args = ap.parse_args()
    names = httpx.get(f"{args.url}/api/v1/label/__name__/values", timeout=10).json()["data"]
    print(f"{len(names)} metric names\n")
    for key, pat in PATTERNS.items():
        hits = [n for n in names if re.search(pat, n, re.IGNORECASE)]
        print(f"{key}:")
        for n in hits[:15]:
            labels = httpx.get(f"{args.url}/api/v1/series", params={"match[]": n}, timeout=10).json()["data"][:1]
            print(f"  {n}  labels={sorted(labels[0].keys()) if labels else []}")
        if not hits:
            print("  (none found)")
        print()
    print("Write the chosen queries into config/rootcause.yaml -> prometheus.queries (see the comments there).")


if __name__ == "__main__":
    main()
