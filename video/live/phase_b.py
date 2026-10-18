"""Phase B (the incident, live): flip paymentFailure in the demo's flag UI, try a checkout, then film RootCause
from the first alarm to the opened pull request, approving the fixes by clicking the real buttons. FalkorDB Browser
shows the BLAMES subgraph during the incident. Saves the PR URL to footage/pr.txt."""
import asyncio

from playwright.async_api import async_playwright

from rec import ROOT, Cast, event, fdb_open, fdb_query, new_page, smooth_scroll


async def wait_text(page, text, timeout_s):
    loc = page.get_by_text(text, exact=False)
    for _ in range(int(timeout_s * 2)):
        if await loc.count():
            return True
        await page.wait_for_timeout(500)
    return False


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True)
        rc = await new_page(b, "http://localhost:8088/")
        fdb = await new_page(b)
        await fdb_open(fdb)
        await rc.wait_for_timeout(2500)
        c_rc = Cast(rc, "b_rc", fps=25)
        await c_rc.start()

        # the bad change, made by hand in the demo's own flag UI
        flags = await new_page(b, "http://localhost:8080/feature")
        c_flags = Cast(flags, "b_flags", fps=30)
        await c_flags.start()
        await flags.wait_for_timeout(2000)
        sel = flags.locator('select[name="paymentFailure"]')
        await sel.scroll_into_view_if_needed()
        await flags.wait_for_timeout(1500)
        await sel.select_option("100%")
        event("flip", flag="paymentFailure", to="100%")
        await flags.wait_for_timeout(3500)
        await c_flags.stop()

        # a customer tries to check out
        shop = await new_page(b, "http://localhost:8080/")
        c_shop = Cast(shop, "b_shop", fps=30)
        await c_shop.start()
        await shop.wait_for_timeout(2000)
        await shop.locator('[data-cy="product-card"]').nth(2).click()
        await shop.wait_for_timeout(2500)
        await shop.locator('[data-cy="product-add-to-cart"]').click()
        await shop.wait_for_url("**/cart", timeout=20000)
        await shop.wait_for_timeout(2500)
        place = shop.locator('[data-cy="checkout-place-order"]')
        await place.scroll_into_view_if_needed()
        await shop.wait_for_timeout(1000)
        try:
            async with shop.expect_response(lambda r: "/api/checkout" in r.url, timeout=30000) as info:
                await place.click()
            resp = await info.value
            event("checkout_response", status=resp.status, body=(await resp.text())[:400])
        except Exception as e:
            event("checkout_response_error", error=str(e)[:200])
        await shop.wait_for_timeout(3000)
        await c_shop.stop()

        # RootCause takes over
        if await wait_text(rc, "just went off", 180):
            event("alarms_seen")
        await rc.wait_for_timeout(6000)
        # FalkorDB: the anomalous subgraph and the BLAMES chain, mid-incident
        c_fdb = Cast(fdb, "b_fdb", fps=30)
        await c_fdb.start()
        await fdb_query(fdb, "MATCH (a:Anomalous)-[b:BLAMES]->(c:Anomalous) RETURN a, b, c")
        await fdb.wait_for_timeout(8000)
        await fdb_query(fdb, "MATCH (a:Service)-[c:CALLS]->(b:Service) RETURN a, c, b")
        await fdb.wait_for_timeout(8000)
        await c_fdb.stop()

        if await wait_text(rc, "What I'm checking", 120):
            event("steps_seen")
            await rc.wait_for_timeout(4000)
            items = rc.locator("li:has(span.font-mono)")
            for i in range(min(await items.count(), 4)):
                try:
                    await items.nth(i).hover(timeout=2000)
                    await rc.wait_for_timeout(1400)
                except Exception:
                    pass
            await rc.mouse.move(10, 10)

        if await wait_text(rc, "Should I fix this?", 300):
            event("fix_prompt")
            await rc.wait_for_timeout(6000)
            await rc.locator("button", has_text="Yes, fix it").last.click()
            event("approve_fix")
        else:
            event("no_fix_prompt")

        if await wait_text(rc, "One more thing", 420):
            event("pr_offer")
            await rc.wait_for_timeout(5000)
            await rc.locator("button", has_text="Yes, open a pull request").last.click()
            event("approve_pr")
        else:
            event("no_pr_offer")

        if await wait_text(rc, "Pull request #", 240):
            await rc.wait_for_timeout(1500)
            href = await rc.locator("a[href*='/pull/']").last.get_attribute("href")
            (ROOT / "pr.txt").write_text(href or "")
            event("pr_open", url=href)
        else:
            event("no_pr")
        await rc.wait_for_timeout(8000)
        await c_rc.stop()

        # the pull request on GitHub (public view)
        href = (ROOT / "pr.txt").read_text().strip() if (ROOT / "pr.txt").exists() else ""
        if href:
            gh = await new_page(b, href)
            c_gh = Cast(gh, "b_gh", fps=30)
            await c_gh.start()
            await gh.wait_for_timeout(4000)
            await smooth_scroll(gh, 700, steps=50, pause=60)
            await gh.wait_for_timeout(3000)
            await gh.goto(href.rstrip("/") + "/files")
            await gh.wait_for_timeout(5000)
            await smooth_scroll(gh, 300, steps=30, pause=60)
            await gh.wait_for_timeout(4000)
            await c_gh.stop()
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
