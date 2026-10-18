"""Draft voice-over with the macOS `say` voice (Samantha). One WAV per scene in voice/, durations in voice/durations.json.
Yash will re-record these lines in his own voice later; the text is the final script."""
import json
import subprocess
import sys
from pathlib import Path

LINES = {
    "s01_hook": "It's 3 AM. Four alarms, two teams, one real cause. RootCause finds it in about a minute, proves it, "
                "fixes it with your OK, and opens the code fix as a pull request.",
    "s02_build": "This is the official OpenTelemetry Demo, a real online shop with nineteen services, running on our laptop. "
                 "Watch RootCause build its graph in FalkorDB from live traffic: every service, every call, every queue, "
                 "updated every five seconds.",
    "s03_github": "Then we connect the shop's GitHub repo. RootCause maps every module, every API it serves and depends on, "
                  "and every line that reads a feature flag, and it flags where the code and the live traffic disagree.",
    "s04_layers": "In FalkorDB, the code layer sits right on top of the live service graph.",
    "s05_break": "Now someone pushes a bad config change: the payment failure flag goes to one hundred percent. "
                 "Checkout starts failing. Nobody tells RootCause anything.",
    "s06_incident": "Alarms fire on payment, checkout, the storefront and the gateway. RootCause sees in the graph that "
                    "they're connected, so it opens one incident instead of four pages. Its Gemini agent investigates "
                    "through our MCP tools, while FalkorDB runs connected components, PageRank and shortest path underneath.",
    "s07_root": "The root cause is payment. The blame trail runs from the gateway down to payment, payment's own requests "
                "are failing, and its flag changed a minute before the alarms. It shows the exact line of code, the "
                "customers who can't check out, and who's on call.",
    "s08_fix": "It offers the safest fix first: switch the flag back, low risk. I approve. RootCause applies it, waits "
               "until every alarm has cleared, and only then marks the incident resolved.",
    "s09_pr": "The flag is off, but the code that failed is still there. So RootCause reads that file from GitHub, Gemini "
              "writes the change, and RootCause opens a real pull request, with the evidence from the graph in the "
              "description. It never merges anything itself. A person reviews the diff, and merges it.",
    "s10_more": "There's more. Predict what breaks before it breaks. Remember past incidents and the fix that worked. "
                "Write the report. And set up your own teams, on-call and runbooks, all in the same graph.",
    "s11_proof": "In fifteen blind tests, RootCause found the cause first eighty percent of the time. Blaming the loudest "
                 "alarm got fifty-three. Gemini on its own tied, but missed the broken connection that only the graph "
                 "could see. That's RootCause.",
}

out = Path(__file__).parent / "voice"
out.mkdir(exist_ok=True)
# `python3 voice.py --mine DIR`: use your own recordings DIR/<key>.(m4a|wav|mp3|aiff), one per line below; a missing
# line falls back to the macOS voice. Then `python render.py` re-times every scene to your voice.
mine = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--mine" else None
durs = {}
for key, text in LINES.items():
    aiff, wav = out / f"{key}.aiff", out / f"{key}.wav"
    own = next((p for ext in ("m4a", "wav", "mp3", "aiff") if mine and (p := mine / f"{key}.{ext}").exists()), None)
    if own is None:
        subprocess.run(["say", "-v", "Samantha", "-r", "172", "-o", str(aiff), text], check=True)
    src = own or aiff
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", "silenceremove=start_periods=1:start_threshold=-45dB",
                    "-ar", "48000", "-ac", "2", str(wav)], check=True)
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                       str(wav)]).decode())
    durs[key] = round(d, 2)
    print(f"{key:14s} {d:5.1f}s  {len(text.split())} words  {'(yours)' if own else '(macOS voice)'}")
(out / "durations.json").write_text(json.dumps(durs, indent=1))
(out / "script.txt").write_text("\n\n".join(LINES.values()) + "\n")
print("total", round(sum(durs.values()), 1), "s")
