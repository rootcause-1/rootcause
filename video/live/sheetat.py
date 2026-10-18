"""sheetat.py out.jpg cast@HH:MM:SS ... -> labelled grid of the frames shown at those wall times."""
import bisect, json, sys, time, datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
out, specs = sys.argv[1], sys.argv[2:]
W, H, cols = 640, 360, 4
rows = (len(specs) + cols - 1) // cols
sheet = Image.new("RGB", (cols * W, rows * (H + 26)), "white")
d = ImageDraw.Draw(sheet); f = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 18)
for i, s in enumerate(specs):
    c, when = s.split("@")
    fr = json.loads((Path("footage") / c / "frames.json").read_text()); ts = [x[1] for x in fr]
    t = time.mktime(time.strptime(datetime.date.today().isoformat() + " " + when, "%Y-%m-%d %H:%M:%S")) if ":" in when else ts[0] + float(when)
    j = max(0, bisect.bisect_right(ts, t) - 1)
    im = Image.open(Path("footage") / c / fr[j][0]).convert("RGB").resize((W, H))
    x, y = (i % cols) * W, (i // cols) * (H + 26)
    sheet.paste(im, (x, y + 26)); d.text((x + 6, y + 3), s, font=f, fill="black")
sheet.save(out, quality=82); print(out, len(specs))
