"""Master take for the demo video: one continuous real run, full pages only, crisp (CSS 1416x797 at DPR 1.25 ->
1770x996 device pixels, JPEG q92). Logs the app's own step bar every 0.5 s (steps.jsonl) and every action
(events.jsonl), so the edit can sync the step tracker and narration to what really happened.
Writes footage2/merge_ready when PR is open on GitHub and waits (up to 12 min) for a person to merge it."""
import asyncio
import base64
import json
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).parent / "footage3"
ROOT.mkdir(exist_ok=True)
CSS_W, CSS_H = 1416, 797   # rendered at a real 1.25 device scale (chrome flag) -> 1768x996 frames
DEV_W, DEV_H = 1770, 996
FORK = "https://github.com/yash4428/opentelemetry-demo"


def event(name, **kw):
    rec = {"t": time.time(), "event": name, **kw}
    with open(ROOT / "events.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(time.strftime("%H:%M:%S"), name, {k: str(v)[:120] for k, v in kw.items()}, flush=True)


def api(path, body=None):
    req = urllib.request.Request("http://localhost:8000" + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json"}, method="GET" if body is None else "POST")
    return json.load(urllib.request.urlopen(req, timeout=30))


class Cast:
    def __init__(self, page, name, fps=30):
        self.page, self.name, self.min_dt = page, name, 1.0 / fps
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
                    if len(self.frames) % 300 == 0:
                        (self.dir / "frames.json").write_text(json.dumps(self.frames))
            finally:
                try:
                    await self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
                except Exception:
                    pass

        self.cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": DEV_W, "maxHeight": DEV_H})
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
    ctx = await browser.new_context(viewport={"width": CSS_W, "height": CSS_H})
    page = await ctx.new_page()
    if url:
        await page.goto(url, wait_until="domcontentloaded")
    return page


async def scroll(page, dy, secs=2.0, x=None, y=None):
    await page.mouse.move(x or CSS_W / 2, y or CSS_H / 2)
    steps = max(1, int(secs * 25))
    for _ in range(steps):
        await page.mouse.wheel(0, dy / steps)
        await page.wait_for_timeout(40)


STEP_JS = """() => {
  const labels = ['Healthy','Alerts','One incident','Investigating','Root cause','Impact','Fix','Fixing','Recovered'];
  const out = [];
  for (const el of document.querySelectorAll('span,div,li,button')) {
    if (el.children.length > 1) continue;
    const t = (el.textContent || '').replace('✓', '').replace(/^\\s*\\d+\\s*/, '').trim();
    if (!labels.includes(t)) continue;
    const r = el.getBoundingClientRect();
    if (r.top > 140 || r.width === 0) continue;
    const bg = getComputedStyle(el).backgroundColor;
    const m = bg.match(/\\d+(\\.\\d+)?/g) || [];
    const dark = m.length >= 3 && (m.length < 4 || +m[3] > 0.5) && (0.3 * m[0] + 0.59 * m[1] + 0.11 * m[2]) < 110;
    out.push([t, dark, (el.textContent || '').includes('✓')]);
  }
  return out;
}"""


async def step_logger(page, stop):
    last = None
    while not stop.is_set():
        try:
            st = await page.evaluate(STEP_JS)
            active = [s[0] for s in st if s[1]]
            done = [s[0] for s in st if s[2]]
            cur = (active[0] if active else None, tuple(done))
            if cur != last:
                with open(ROOT / "steps.jsonl", "a") as f:
                    f.write(json.dumps({"t": time.time(), "active": cur[0], "done": list(cur[1])}) + "\n")
                last = cur
        except Exception:
            pass
        await asyncio.sleep(0.5)


async def wait_text(page, text, timeout_s):
    loc = page.get_by_text(text, exact=False)
    for _ in range(int(timeout_s * 2)):
        if await loc.count():
            return True
        await page.wait_for_timeout(500)
    return False


async def fdb_open(page):
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
    await page.get_by_text("rc_live", exact=True).first.click()
    await page.wait_for_timeout(2000)


async def fdb_query(page, name, cypher, wait=8000):
    ed = page.locator(".monaco-editor").first
    await ed.click()
    await page.keyboard.press("Meta+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.insert_text(cypher)
    await page.wait_for_timeout(500)
    await page.keyboard.press("Escape")
    await page.locator("button.px-4.bg-primary").filter(has_text="RUN").first.click()
    event("fdb_query", shot=name, cypher=cypher)
    await page.wait_for_timeout(wait)


async def main():
    stop = asyncio.Event()
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True, args=["--force-device-scale-factor=1.25"])
        rc = await new_page(b, "http://localhost:8088/")
        await rc.wait_for_timeout(3000)
        logger = asyncio.ensure_future(step_logger(rc, stop))
        c_rc = Cast(rc, "rc", fps=30)
        await c_rc.start()
        await rc.wait_for_timeout(4000)
        event("reset", result=api("/api/admin/reset", {}))
        await rc.wait_for_timeout(45000)

        # the shop, healthy
        shop = await new_page(b, "http://localhost:8080/")
        c = Cast(shop, "shop_healthy")
        await c.start()
        await shop.wait_for_timeout(3500)
        await scroll(shop, 700, 3.0)
        await shop.wait_for_timeout(1500)
        await shop.locator('[data-cy="product-card"]').first.click()
        await shop.wait_for_timeout(3500)
        await shop.locator('[data-cy="product-add-to-cart"]').click()
        await shop.wait_for_timeout(4000)
        await c.stop()

        # connect GitHub on camera
        await rc.get_by_role("button", name="Codebase").first.click()
        event("codebase_open")
        await rc.wait_for_timeout(2500)
        box = rc.get_by_label("GitHub repository URL")
        await box.click()
        await box.fill("")
        await box.type(FORK, delay=55)
        await rc.wait_for_timeout(800)
        await rc.get_by_role("button", name="Scan").click()
        event("scan_click")
        await rc.wait_for_timeout(1500)
        for _ in range(120):
            if not await rc.get_by_role("button", name="Scanning…").count():
                break
            await rc.wait_for_timeout(500)
        event("scan_done")
        await rc.wait_for_timeout(4000)
        await scroll(rc, 650, 4.0, x=CSS_W - 230, y=CSS_H / 2)
        await rc.wait_for_timeout(4000)
        await scroll(rc, 1400, 5.0, x=CSS_W - 230, y=CSS_H / 2)
        event("drift_view")
        await rc.wait_for_timeout(5000)
        await rc.get_by_role("button", name="Close").first.click()
        event("codebase_close")
        await rc.wait_for_timeout(1500)

        # FalkorDB: the service layer and the code layer
        fdb = await new_page(b)
        await fdb_open(fdb)
        c = Cast(fdb, "fdb_layers")
        await c.start()
        await fdb.wait_for_timeout(1500)
        await fdb_query(fdb, "calls", "MATCH (a:Service)-[c:CALLS]->(b:Service) RETURN a, c, b", wait=9000)
        await fdb_query(fdb, "code", "MATCH (m:CodeModule)-[i:IMPLEMENTS]->(s:Service)-[c:CALLS]->(t:Service) "
                                     "RETURN m, i, s, c, t", wait=10000)
        await c.stop()

        # baselines learned, a few healthy ticks
        for _ in range(400):
            if not api("/api/status").get("learning_left_ms"):
                break
            await rc.wait_for_timeout(2000)
        event("learned")
        await rc.wait_for_timeout(12000)

        # the bad change, in the demo's own flag page
        flags = await new_page(b, "http://localhost:8080/feature")
        c = Cast(flags, "flags")
        await c.start()
        await flags.wait_for_timeout(2500)
        sel = flags.locator('select[name="paymentFailure"]')
        await sel.scroll_into_view_if_needed()
        await flags.wait_for_timeout(2500)
        await sel.select_option("100%")
        event("flip", flag="paymentFailure", to="100%")
        await flags.wait_for_timeout(4500)
        await c.stop()

        # a customer tries to pay
        shop2 = await new_page(b, "http://localhost:8080/")
        c = Cast(shop2, "shop_fail")
        await c.start()
        await shop2.wait_for_timeout(2500)
        await shop2.locator('[data-cy="product-card"]').nth(2).click()
        await shop2.wait_for_timeout(3000)
        await shop2.locator('[data-cy="product-add-to-cart"]').click()
        await shop2.wait_for_url("**/cart", timeout=20000)
        await shop2.wait_for_timeout(3000)
        place = shop2.locator('[data-cy="checkout-place-order"]')
        await place.scroll_into_view_if_needed()
        await shop2.wait_for_timeout(1500)
        try:
            async with shop2.expect_response(lambda r: "/api/checkout" in r.url, timeout=30000) as info:
                await place.click()
            resp = await info.value
            event("checkout_response", status=resp.status, body=(await resp.text())[:400])
        except Exception as e:
            event("checkout_response_error", error=str(e)[:200])
        await shop2.wait_for_timeout(3500)
        await c.stop()

        # RootCause, live
        for txt, name, tmo in (("just went off", "alarms", 240), ("one incident", "incident", 120)):
            if await wait_text(rc, txt, tmo):
                event(name)
        # FalkorDB mid-incident: the BLAMES subgraph
        await rc.wait_for_timeout(5000)
        c = Cast(fdb, "fdb_blames")
        await c.start()
        await fdb_query(fdb, "blames", "MATCH (a:Anomalous)-[b:BLAMES]->(c:Anomalous) RETURN a, b, c", wait=9000)
        await c.stop()

        for txt, name, tmo in (("What I'm checking", "investigating", 120), ("Found it", "root_cause", 180),
                               ("Who it hurts", "impact", 120)):
            if await wait_text(rc, txt, tmo):
                event(name)
        btn = rc.locator("button", has_text="Yes, fix it")
        for _ in range(600):
            if await btn.count():
                break
            await rc.wait_for_timeout(500)
        event("fix_prompt")
        await rc.wait_for_timeout(7000)
        await btn.last.click()
        event("approve_fix")

        if await wait_text(rc, "All clear", 420):
            event("recovered")
        pr_btn = rc.locator("button", has_text="Yes, open a pull request")
        for _ in range(240):
            if await pr_btn.count():
                break
            await rc.wait_for_timeout(500)
        event("pr_offer")
        await rc.wait_for_timeout(6000)
        while time.time() < 1792318600.0:  # the API allows one fix PR per 10 minutes; the previous one opened 15:36
            await rc.wait_for_timeout(1000)
        await pr_btn.last.click()
        event("approve_pr")
        href = ""
        for _ in range(480):
            link = rc.locator("a[href*='/pull/']")
            if await link.count():
                href = await link.last.get_attribute("href") or ""
                break
            if await rc.get_by_text("couldn't open the pull request", exact=False).count():
                event("pr_failed")
                break
            await rc.wait_for_timeout(500)
        event("pr_open", url=href)
        await rc.wait_for_timeout(10000)
        await c_rc.stop()

        # the pull request on GitHub, then wait for a person to merge it
        if href:
            gh = await new_page(b, href)
            c = Cast(gh, "github")
            await c.start()
            await gh.wait_for_timeout(5000)
            await scroll(gh, 750, 5.0)
            await gh.wait_for_timeout(4000)
            await gh.goto(href.rstrip("/") + "/files")
            event("gh_files")
            await gh.wait_for_timeout(6000)
            await scroll(gh, 250, 2.0)
            await gh.wait_for_timeout(4000)
            await gh.goto(href)
            await gh.wait_for_timeout(2000)
            (ROOT / "merge_ready").write_text(href)
            event("merge_wait", url=href)
            for _ in range(144):
                await gh.wait_for_timeout(5000)
                if await gh.locator("[data-status='pullMerged']").count():
                    break
                await gh.reload(wait_until="domcontentloaded")
            event("merged_seen")
            await gh.wait_for_timeout(4000)
            await scroll(gh, 1100, 4.0)
            await gh.wait_for_timeout(4000)
            await c.stop()

        # the rest of the app
        c = Cast(rc, "tabs")
        await c.start()
        await rc.wait_for_timeout(2500)
        await rc.get_by_role("button", name="Predict").first.click()
        await rc.wait_for_timeout(2000)
        await rc.get_by_label("Service to break").select_option("payment")
        await rc.wait_for_timeout(1200)
        await rc.locator("button", has_text="Predict").last.click()
        event("tab", tab="Predict")
        await rc.wait_for_timeout(6000)
        for tab in ("Memory", "Reports", "Your company", "Break something"):
            await rc.get_by_role("button", name=tab).first.click()
            event("tab", tab=tab)
            await rc.wait_for_timeout(3000)
            if tab == "Reports":
                rep = rc.locator("button:has-text('INC-')").first
                if await rep.count():
                    await rep.click()
                await rc.wait_for_timeout(2000)
                await scroll(rc, 600, 4.0)
            if tab == "Your company":
                await scroll(rc, 500, 3.0)
            await rc.wait_for_timeout(3000)
        await c.stop()

        # FalkorDB: the whole story as one graph
        c = Cast(fdb, "fdb_final")
        await c.start()
        await fdb_query(fdb, "alerts", "MATCH (a:Alert)-[p:PART_OF]->(i:Incident) MATCH (a)-[f:FIRED_ON]->(s) "
                                       "RETURN a, p, i, f, s", wait=8000)
        await fdb_query(fdb, "steps", "MATCH (i:Incident)-[x:INVESTIGATED_BY]->(st:Step) OPTIONAL MATCH (st)-[c:CITED]->(n) "
                                      "RETURN i, x, st, c, n", wait=8000)
        await fdb_query(fdb, "pr", "MATCH (p:PullRequest)-[f:FIXES]->(i:Incident)-[rc:ROOT_CAUSE]->(r) "
                                   "OPTIONAL MATCH (p)-[c:CHANGES]->(m:CodeModule) OPTIONAL MATCH (m)-[im:IMPLEMENTS]->(s:Service) "
                                   "RETURN p, f, i, rc, r, c, m, im, s", wait=8000)
        await c.stop()

        gh2 = await new_page(b, "https://github.com/rootcause-1/rootcause#scorecard")
        await gh2.wait_for_timeout(3000)
        h = gh2.locator("h2:has-text('Scorecard')").first
        if await h.count():
            await h.scroll_into_view_if_needed()
        c = Cast(gh2, "scorecard")
        await c.start()
        await gh2.wait_for_timeout(3000)
        await scroll(gh2, 300, 3.0)
        await gh2.wait_for_timeout(5000)
        await c.stop()
        stop.set()
        await logger
        event("done")
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
