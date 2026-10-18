# Live demo video (18 Oct 2026)

The 2:31 demo video cut from a **real run** on Yash's laptop: the OpenTelemetry Demo shop, RootCause in live mode
with the Gemini agent, the fork `yash4428/opentelemetry-demo` on GitHub, and the FalkorDB Browser. Nothing is
mocked. Every shot is a screencast of the real pages, and every number on screen comes from that run.

Output: `out/rootcause-demo.mp4` (1920×1080, 30 fps). A copy is in `../out/rootcause-demo-draft.mp4`.
The draft voice is macOS "Samantha". Footage (3 GB), voice and renders are gitignored and live only on Yash's Mac.

## Swap in your own voice
1. Record one file per line of `voice/script.txt` (same order), named after the keys in `voice.py`:
   `s01_hook`, `s02_build`, `s03_github`, `s04_layers`, `s05_break`, `s06_incident`, `s07_root`, `s08_fix`,
   `s09_pr`, `s10_more`, `s11_proof` (`.m4a`, `.wav`, `.mp3` or `.aiff`, for example from QuickTime or Voice Memos).
2. `python3 voice.py --mine ~/Desktop/vo` (a missing line falls back to the macOS voice).
3. `uv run --no-project --with pillow python render.py` re-times every scene to your voice and writes the video.
Keep each line about as long as the macOS one. The whole video must stay under 3:00.

## How it was recorded
| Script | Films |
|---|---|
| `monitor.py` | `redis-cli MONITOR` on FalkorDB → `footage/monitor.log` (the real query stream in the overlay) |
| `phase_a.py` | reset → the map filling from live traces · the healthy shop · Codebase scan of the fork · FalkorDB service and code layers |
| `phase_b.py` | flip `paymentFailure` in the demo's flag page · a failing checkout (real 422 response) · the incident |
| `phase_b2.py` | take 2 rescue: fix prompt → approve → verified recovery → "Yes, open a pull request" → PR #2 on GitHub |
| `phase_c.py` | Predict, Memory, Reports, Your company · scorecard on GitHub · `merged` = waits until a person merges the PR |
| `phase_e.py` | FalkorDB Browser: alerts → incident, the agent's Step trail, incident → PR → code module |
| `render.py` + `scenes.py` | the edit: real footage under each voice line, speed-ups labelled, zooms, captions |

Honest notes (also in `scenes.py`):
- Take 1's PR failed: Gemini needed more than 60 s to write the change. The timeout is now 180 s (commit `a8de317`).
- Take 2's recorder matched chat text left over from an earlier incident. So its map footage is used without the
  chat, and the chat comes from a fresh page load (`b2_rc`).
- The live UI container was built before the switch to Gemini, so two chat lines said "Claude". The backend used
  Gemini (API logs; the PR text says "Change written by Gemini"). Those two lines are kept out of frame, and the
  UI container has been rebuilt since.
- The FalkorDB "alerts → incident" and Step-trail shots were filmed right after the incident, from the stored graph.
