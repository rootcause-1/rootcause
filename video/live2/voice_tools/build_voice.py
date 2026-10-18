"""Build per-segment voice files from the user's recordings: sentence spans from align.json, edges trimmed,
long pauses (> 0.5 s of silence between words) shortened to 0.3 s. Writes OUT/<seg>.wav + OUT/timing.json."""
import json, sys
import numpy as np, soundfile as sf
OUT = sys.argv[1]
A = json.load(open("align.json")); W = json.load(open("words.json"))
full = {f: sf.read(f"full{f}.wav", dtype="float32")[0] for f in range(1, 6)}
SR, MAXGAP, KEEP, JOIN = 48000, 0.38, 0.26, 0.2
def db(x): return 20 * np.log10(np.sqrt((x ** 2).mean() + 1e-12)) if len(x) else -120
timing, report = {}, []
for seg, rows in A.items():
    groups = []
    for j, r in enumerate(rows):
        if groups and groups[-1]["file"] == r["file"]:
            groups[-1]["e"] = max(groups[-1]["e"], r["e"]); groups[-1]["sent"].append((j, r["s"]))
        else:
            groups.append({"file": r["file"], "s": r["s"], "e": r["e"], "sent": [(j, r["s"])]})
    pieces, starts, t = [], {}, 0.0
    for gi, g in enumerate(groups):
        f = g["file"]; ws = [w for w in W[str(f)] if g["s"] - 0.05 <= w["s"] and w["e"] <= g["e"] + 0.05]
        # cut points: long silent gaps between consecutive words
        cuts = []
        for a, b in zip(ws, ws[1:]):
            gap = b["s"] - a["e"]
            if gap > MAXGAP and db(full[f][int((a["e"] + 0.05) * SR): int((b["s"] - 0.05) * SR)]) < -42:
                cuts.append((a["e"] + 0.08, b["s"] - 0.08))
        # walk the group, skipping the middle of long gaps
        pos, src = g["s"], []
        for c0, c1 in cuts:
            src.append((pos, c0)); pos = c1
        src.append((pos, g["e"]))
        removed = 0.0
        if gi: pieces.append(np.zeros((int(JOIN * SR), 2), np.float32)); t += JOIN
        g0_t = t
        for k, (a, b) in enumerate(src):
            seg_audio = full[f][int(a * SR): int(b * SR)].copy()
            fade = int(0.012 * SR)
            if len(seg_audio) > 2 * fade:
                seg_audio[:fade] *= np.linspace(0, 1, fade)[:, None]; seg_audio[-fade:] *= np.linspace(1, 0, fade)[:, None]
            pieces.append(seg_audio); t += len(seg_audio) / SR
            if k < len(src) - 1:
                pieces.append(np.zeros((int((KEEP - 0.16) * SR), 2), np.float32)); t += KEEP - 0.16
        # sentence start offsets inside this group, after the removed silence
        for j, s0 in g["sent"]:
            off = s0 - g["s"] - sum(max(0, min(c1, s0) - c0) - (KEEP - 0.16 if s0 > c1 else 0) for c0, c1 in cuts if c0 < s0)
            starts[j] = round(g0_t + max(0, off), 3)
    audio = np.concatenate(pieces)
    # trim leading / trailing silence by loudness (whisper puts a file's first word at 0.0 s)
    mono = np.abs(audio).mean(1); w = int(0.02 * SR); n = len(mono) // w
    lv = 20 * np.log10(np.sqrt((mono[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9)
    voiced = np.where(lv > -42)[0]
    lead = max(0, voiced[0] * w - int(0.05 * SR)) if len(voiced) else 0
    end = min(len(audio), (voiced[-1] + 1) * w + int(0.12 * SR)) if len(voiced) else len(audio)
    audio = audio[lead:end]
    sh = lead / SR
    sf.write(f"{OUT}/{seg}.wav", audio, SR)
    timing[seg] = {"dur": round(len(audio) / SR, 3), "starts": [round(max(0.0, starts[j] - sh), 3) for j in range(len(rows))]}
    report.append((seg + ":lead", round(sh, 2)))
json.dump(timing, open(f"{OUT}/timing.json", "w"), indent=1)
tot = sum(v["dur"] for v in timing.values())
print("segments", len(timing), "| voice total", round(tot, 1), "s | lead trims:", [(s, v) for s, v in report if s.endswith(":lead") and v > 0.1])
for seg, v in timing.items(): print(f"  {seg:12s} {v['dur']:5.1f}s  starts {v['starts']}")
