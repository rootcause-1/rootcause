"""grab.py out.jpg cast@HH:MM:SS ... : full-res frames (by file mtime, works while a cast is still recording) in a grid."""
import sys, os, time, datetime, bisect
from pathlib import Path
from PIL import Image
out, specs = sys.argv[1], sys.argv[2:]
ims = []
for s in specs:
    c, when = s.split("@"); d = Path(__file__).parent / "footage3" / c
    files = sorted(d.glob("*.jpg")); ts = [f.stat().st_mtime for f in files]
    t = time.mktime(time.strptime(datetime.date.today().isoformat() + " " + when, "%Y-%m-%d %H:%M:%S"))
    ims.append(Image.open(files[max(0, bisect.bisect_right(ts, t) - 1)]).convert("RGB"))
w, h = ims[0].size; cols = 2; rows = (len(ims) + 1) // 2
sheet = Image.new("RGB", (w * cols // 2, h * rows // 2), "white")
for i, im in enumerate(ims): sheet.paste(im.resize((w // 2, h // 2)), ((i % 2) * w // 2, (i // 2) * h // 2))
sheet.save(out, quality=88); print(out)
