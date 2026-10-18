"""Phase A (healthy): reset the graph and film it filling from live traffic, browse the shop, connect GitHub
(Codebase scan of the fork), and show the service + code layers in FalkorDB Browser. Ends when baselines are learned."""
import asyncio

from playwright.async_api import async_playwright

from rec import Cast, api, event, fdb_open, fdb_query, new_page, smooth_scroll

FORK = "https://github.com/yash4428/opentelemetry-demo"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True)
        rc = await new_page(b, "http://localhost:8088/")
        await rc.wait_for_timeout(3000)
        c_rc = Cast(rc, "a_rc", fps=20)
        await c_rc.start()
        await rc.wait_for_timeout(2500)
        event("reset", result=api("/api/admin/reset", {}))
        await rc.wait_for_timeout(40000)  # the map fills as spans arrive

        # the shop, healthy
        shop = await new_page(b, "http://localhost:8080/")
        c_shop = Cast(shop, "a_shop", fps=30)
        await c_shop.start()
        await shop.wait_for_timeout(3000)
        await smooth_scroll(shop, 900, steps=40)
        await shop.wait_for_timeout(800)
        await shop.locator('[data-cy="product-card"]').first.click()
        await shop.wait_for_timeout(3000)
        await shop.locator('[data-cy="product-add-to-cart"]').click()
        await shop.wait_for_timeout(4000)
        event("shop_cart", url=shop.url)
        await c_shop.stop()

        # connect GitHub (scan the fork) on camera
        await rc.get_by_role("button", name="Codebase").first.click()
        await rc.wait_for_timeout(1500)
        box = rc.get_by_label("GitHub repository URL")
        await box.click()
        await box.fill("")
        await box.type(FORK, delay=35)
        await rc.wait_for_timeout(600)
        await rc.get_by_role("button", name="Scan").click()
        event("scan_click")
        for _ in range(120):
            await rc.wait_for_timeout(1000)
            if not await rc.get_by_role("button", name="Scanning…").count():
                break
        event("scan_done")
        await rc.wait_for_timeout(2500)
        panel = rc.locator("text=Services and their code").first
        if await panel.count():
            await panel.scroll_into_view_if_needed()
        await rc.wait_for_timeout(2500)
        await smooth_scroll(rc, 700, steps=40, pause=60)
        await rc.wait_for_timeout(2500)
        await smooth_scroll(rc, 900, steps=40, pause=60)  # drift: code vs live traffic
        await rc.wait_for_timeout(4000)
        await rc.get_by_role("button", name="Close").first.click()
        await rc.wait_for_timeout(1000)

        # FalkorDB Browser: service layer, then code layer
        fdb = await new_page(b)
        await fdb_open(fdb)
        c_fdb = Cast(fdb, "a_fdb", fps=30)
        await c_fdb.start()
        await fdb.wait_for_timeout(1000)
        await fdb_query(fdb, "MATCH (a:Service)-[c:CALLS]->(b:Service) RETURN a, c, b")
        await fdb.wait_for_timeout(9000)
        await fdb_query(fdb, "MATCH (m:CodeModule)-[i:IMPLEMENTS]->(s:Service)-[c:CALLS]->(t:Service) RETURN m, i, s, c, t")
        await fdb.wait_for_timeout(10000)
        await c_fdb.stop()

        # wait for baselines, keep filming the map
        for _ in range(400):
            st = api("/api/status")
            if not st.get("learning_left_ms"):
                break
            await rc.wait_for_timeout(2000)
        event("learned")
        await rc.wait_for_timeout(5000)
        await c_rc.stop()
        await b.close()


asyncio.run(main())
