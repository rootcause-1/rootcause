"""Send a shopping prompt to the demo's AI agent every N seconds (the AI-agent flags need traffic to show).

Usage: python scripts/assistant_traffic.py --url <agent POST /prompt URL> [--every 20]
The URL is a VERIFY item (read the demo's compose.agent.yaml); also set demo.agent_prompt_url in the config.
"""

import argparse
import itertools
import time

import httpx

PROMPTS = [
    "Find me a telescope under $300 and add it to my cart.",
    "What accessories go well with a beginner telescope?",
    "Recommend a book about astronomy and tell me its price.",
    "Is there a discount on solar filters right now?",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--every", type=float, default=20.0)
    args = ap.parse_args()
    for prompt in itertools.cycle(PROMPTS):
        t0 = time.time()
        try:
            r = httpx.post(args.url, json={"prompt": prompt}, timeout=120)
            print(f"{r.status_code} in {time.time() - t0:.1f}s: {prompt}")
        except Exception as exc:
            print(f"error: {exc}")
        time.sleep(args.every)


if __name__ == "__main__":
    main()
