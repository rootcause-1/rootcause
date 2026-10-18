"""Voice every sentence with Kokoro (open source, Apache-2.0). Writes voice2/<seg>.wav (48 kHz stereo) and
voice2/timing.json = {seg: {"dur": s, "starts": [sentence start offsets]}}. tts2.py [seg ...] to redo some."""
import json, sys
import numpy as np, soundfile as sf
from pathlib import Path
from kokoro_onnx import Kokoro
from script2 import SEGMENTS, speak
VOICE, SPEED, GAP = "af_heart", 1.27, 0.14
out = Path(__file__).parent / "voice2"; out.mkdir(exist_ok=True)
tj = out / "timing.json"
timing = json.loads(tj.read_text()) if tj.exists() else {}
only = set(sys.argv[1:])
k = Kokoro("tts_models/kokoro-v1.0.onnx", "tts_models/voices-v1.0.bin")
for seg, sentences in SEGMENTS:
    if only and seg not in only:
        continue
    parts, starts, t = [], [], 0.0
    for s in sentences:
        a, sr = k.create(speak(s), voice=VOICE, speed=SPEED, lang="en-us")
        a = np.trim_zeros(a, "fb") if a.size else a
        starts.append(round(t, 3)); parts.append(a); t += len(a) / sr
        gap = np.zeros(int(GAP * sr), dtype=a.dtype); parts.append(gap); t += GAP
    audio = np.concatenate(parts[:-1])
    # 24 kHz mono -> 48 kHz stereo (linear resample is fine for speech)
    x = np.interp(np.arange(0, len(audio), 0.5), np.arange(len(audio)), audio).astype(np.float32)
    sf.write(out / f"{seg}.wav", np.stack([x, x], 1), 48000)
    timing[seg] = {"dur": round(len(audio) / sr, 3), "starts": starts}
    print(f"{seg:12s} {timing[seg]['dur']:5.1f}s  {sum(len(s.split()) for s in sentences)} words")
tj.write_text(json.dumps(timing, indent=1))
print("total", round(sum(v["dur"] for v in timing.values()), 1), "s")
