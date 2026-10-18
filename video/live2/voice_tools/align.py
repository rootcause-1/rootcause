"""Map every script sentence to the user's recordings (word timestamps), refine the edges with the audio energy."""
import difflib, json, re, sys
import numpy as np, soundfile as sf
sys.path.insert(0, "/Users/yashaggarwal/Desktop/graphhacks/rootcause/video/live2")
from script2 import SEGMENTS
W = json.load(open("words.json"))
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower().replace("falkordb", "falkor"))
words = [(int(f), w["s"], w["e"], norm(w["w"])) for f in sorted(W, key=int) for w in W[f] if norm(w["w"])]
toks = [w[3] for w in words]
script = []  # (seg, sentence index, token)
for seg, sents in SEGMENTS:
    for j, s in enumerate(sents):
        for t in s.split():
            if norm(t):
                script.append((seg, j, norm(t)))
sm = difflib.SequenceMatcher(a=[x[2] for x in script], b=toks, autojunk=False)
amap = {}
for a, b, n in sm.get_matching_blocks():
    for k in range(n):
        amap[a + k] = b + k
audio = {f: sf.read(f"rec{f}.wav", dtype="float32")[0] for f in range(1, 6)}
SR = 16000
def energy_db(f, t0, t1):
    a = audio[f][int(max(0, t0) * SR): int(t1 * SR)]
    return 20 * np.log10(np.sqrt((a ** 2).mean() + 1e-12)) if len(a) else -120
def refine(f, s, e):
    for _ in range(6):                     # extend start back while still voiced (up to 0.3 s)
        if energy_db(f, s - 0.05, s) > -40: s -= 0.05
        else: break
    for _ in range(10):                    # extend end while still voiced (up to 0.5 s)
        if energy_db(f, e, e + 0.05) > -40: e += 0.05
        else: break
    return max(0, s - 0.04), min(len(audio[f]) / SR, e + 0.10)
out, worst = {}, []
for i, (seg, sents) in enumerate(SEGMENTS):
    for j in range(len(sents)):
        idx = [k for k, x in enumerate(script) if x[0] == seg and x[1] == j]
        hit = [amap[k] for k in idx if k in amap]
        cover = len(hit) / len(idx)
        if not hit:
            print("NOT FOUND", seg, j); continue
        b0, b1 = min(hit), max(hit)
        f0, f1 = words[b0][0], words[b1][0]
        if f0 != f1:   # a sentence never spans files: keep the part in the file holding most of it
            f0 = f1 = max({words[h][0] for h in hit}, key=lambda f: sum(words[h][0] == f for h in hit))
            hh = [h for h in hit if words[h][0] == f0]; b0, b1 = min(hh), max(hh)
        s, e = refine(f0, words[b0][1], words[b1][2])
        out.setdefault(seg, []).append({"file": f0, "s": round(s, 3), "e": round(e, 3), "cover": round(cover, 2),
                                        "heard": " ".join(W[str(f0)][k]["w"] for k in range(len(W[str(f0)]))
                                                          if s <= W[str(f0)][k]["s"] < e)[:90]})
        worst.append((cover, seg, j))
json.dump(out, open("align.json", "w"), indent=1)
for seg, rows in out.items():
    tot = sum(r["e"] - r["s"] for r in rows)
    print(f"{seg:12s} {tot:5.1f}s  " + " | ".join(f"f{r['file']} {r['s']:.1f}-{r['e']:.1f} ({r['cover']:.0%})" for r in rows))
print("lowest coverage:", sorted(worst)[:5])
