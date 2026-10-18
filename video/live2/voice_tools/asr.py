"""Word-level transcription of the five recordings (faster-whisper small.en, CPU int8) -> words.json"""
import json, time
import soundfile as sf, numpy as np
from faster_whisper import WhisperModel
m = WhisperModel("small.en", device="cpu", compute_type="int8")
out = {}
for i in range(1, 6):
    t0 = time.time()
    audio, _sr = sf.read(f"rec{i}.wav", dtype="float32")
    segs, info = m.transcribe(audio, word_timestamps=True, beam_size=5, vad_filter=False,
                              initial_prompt="RootCause, FalkorDB, OpenTelemetry, Gemini, MCP, GitHub, gRPC, PageRank, BLAMES.")
    words = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for s in segs for w in s.words]
    out[i] = words
    print(i, len(words), "words", round(time.time() - t0, 1), "s |", " ".join(x["w"] for x in words[:18]), "...", " ".join(x["w"] for x in words[-10:]), flush=True)
json.dump(out, open("words.json", "w"), indent=0)
