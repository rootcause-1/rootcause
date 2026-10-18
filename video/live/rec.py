"""Recording helpers for the demo video: CDP screencast per page -> JPEG frames with wall-clock timestamps,
plus an event log so scenes can be cut by time later. Nothing here changes the system under test except the
clicks each phase script makes on purpose (logged in events.jsonl)."""
import asyncio
import base64
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent / "footage"
ROOT.mkdir(exist_ok=True)
W, H = 1920, 1080


def event(name, **kw):
    rec = {"t": time.time(), "event": name, **kw}
    with open(ROOT / "events.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(time.strftime("%H:%M:%S"), name, kw or "", flush=True)


def api(path, body=None):
    req = urllib.request.Request("http://localhost:8000" + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json"}, method="GET" if body is None else "POST")
    return json.load(urllib.request.urlopen(req, timeout=30))


class Cast:
    """Screencast one page into footage/<name>/ (frames.json = [[file, wallclock_ts], ...])."""

    def __init__(self, page, name, fps=30, quality=82):
        self.page, self.name, self.min_dt, self.quality = page, name, 1.0 / fps, quality
        self.dir = ROOT / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.frames, self.last, self.cdp = [], 0.0, None

    async def start(self):
        self.cdp = await self.page.context.new_cdp_session(self.page)

        async def on_frame(ev):
            ts = ev["metadata"]["timestamp"]
            try:
                if ts - self.last >= self.min_dt:
                    self.last = ts
                    fn = f"{len(self.frames):06d}.jpg"
                    (self.dir / fn).write_bytes(base64.b64decode(ev["data"]))
                    self.frames.append([fn, ts])
            finally:
                await self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})

        self.cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": self.quality, "maxWidth": W, "maxHeight": H,
                                                     "everyNthFrame": 1})
        event("cast_start", cast=self.name)

    async def stop(self):
        try:
            await self.cdp.send("Page.stopScreencast")
        except Exception:
            pass
        await asyncio.sleep(0.3)
        (self.dir / "frames.json").write_text(json.dumps(self.frames))
        event("cast_stop", cast=self.name, frames=len(self.frames))


async def new_page(browser, url=None):
    ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
    page = await ctx.new_page()
    if url:
        await page.goto(url, wait_until="domcontentloaded")
    return page


async def smooth_scroll(page, dy, steps=30, pause=40, x=960, y=600):
    await page.mouse.move(x, y)
    for _ in range(steps):
        await page.mouse.wheel(0, dy / steps)
        await page.wait_for_timeout(pause)


async def fdb_open(page, graph="rc_live"):
    await page.goto("http://localhost:3300/")
    await page.wait_for_timeout(2000)
    if "/login" in page.url:
        await page.click("#submit-button")
        await page.wait_for_timeout(3000)
    sk = page.get_by_role("button", name="Skip Tutorial")
    if await sk.count():
        await sk.first.click()
        await page.wait_for_timeout(800)
    await page.get_by_role("button", name="Select Graph").first.click()
    await page.wait_for_timeout(1200)
    await page.get_by_text(graph, exact=True).first.click()
    await page.wait_for_timeout(1500)


async def fdb_query(page, cypher, type_it=True):
    ed = page.locator(".monaco-editor").first
    await ed.click()
    await page.keyboard.press("Meta+A")
    await page.keyboard.press("Backspace")
    if type_it:
        await page.keyboard.type(cypher, delay=18)
    else:
        await page.keyboard.insert_text(cypher)
    await page.keyboard.press("Escape")
    await page.locator("button.px-4.bg-primary").filter(has_text="RUN").first.click()
    event("fdb_query", cypher=cypher)
