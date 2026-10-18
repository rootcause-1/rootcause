import numpy as np, soundfile as sf, json, sys
D = sys.argv[1]; T = json.load(open(f"{D}/timing.json")); target = -20.0
for seg in T:
    p = f"{D}/{seg}.wav"; a, sr = sf.read(p, dtype="float32"); m = a.mean(1)
    w = int(0.05 * sr); n = len(m) // w; r = np.sqrt((m[: n * w].reshape(n, w) ** 2).mean(1) + 1e-12); db = 20 * np.log10(r)
    v = db[db > -40]; lvl = 20 * np.log10(np.sqrt(np.mean((10 ** (v / 20)) ** 2))) if len(v) else -30
    b = a * 10 ** ((target - lvl) / 20); pk = np.abs(b).max()
    sf.write(p, b * (0.95 / pk) if pk > 0.95 else b, sr)
print("levelled", len(T))
