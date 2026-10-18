"""Phase C (after the incident): the feature montage (Predict, Memory, Reports, Your company), the incident + pull
request in FalkorDB Browser, and the generated scorecard on GitHub. `python phase_c.py merged` only films the merged PR."""
import asyncio
import sys

from playwright.async_api import async_playwright

from rec import ROOT, Cast, event, fdb_open, fdb_query, new_page, smooth_scroll

PR_QUERY = ("MATCH (p:PullRequest)-[f:FIXES]->(i:Incident)-[rc:ROOT_CAUSE]->(r) "
            "OPTIONAL MATCH (p)-[c:CHANGES]->(m:CodeModule) OPTIONAL MATCH (i)<-[po:PART_OF]-(a:Alert) "
            "RETURN p, f, i, rc, r, c, m, po, a")


async def montage(b):
    rc = await new_page(b, "http://localhost:8088/")
    await rc.wait_for_timeout(3000)
    c = Cast(rc, "c_rc", fps=25)
    await c.start()
    await rc.wait_for_timeout(1500)
    await rc.get_by_role("button", name="Predict").first.click()
    await rc.wait_for_timeout(1500)
    await rc.get_by_label("Service to break").select_option("payment")
    await rc.wait_for_timeout(800)
    await rc.locator("button", has_text="Predict").last.click()
    event("predict")
    await rc.wait_for_timeout(5500)
    for tab in ("Memory", "Reports", "Your company"):
        await rc.get_by_role("button", name=tab).first.click()
        event("tab", tab=tab)
        await rc.wait_for_timeout(2500)
        if tab == "Reports":
            btn = rc.locator("button:has-text('INC-')").first
            if await btn.count():
                await btn.click()
            await rc.wait_for_timeout(1500)
            await smooth_scroll(rc, 500, steps=30, pause=50)
        if tab == "Your company":
            await smooth_scroll(rc, 400, steps=30, pause=50)
        await rc.wait_for_timeout(2500)
    await c.stop()

    fdb = await new_page(b)
    await fdb_open(fdb)
    cf = Cast(fdb, "c_fdb", fps=30)
    await cf.start()
    await fdb_query(fdb, PR_QUERY, type_it=False)
    await fdb.wait_for_timeout(9000)
    await cf.stop()

    gh = await new_page(b, "https://github.com/rootcause-1/rootcause#scorecard")
    await gh.wait_for_timeout(2500)
    anchor = gh.locator("a[href='#scorecard'], h2:has-text('Scorecard')").first
    if await anchor.count():
        await anchor.scroll_into_view_if_needed()
    cs = Cast(gh, "c_score", fps=30)
    await cs.start()
    await gh.wait_for_timeout(2500)
    await smooth_scroll(gh, 450, steps=40, pause=60)
    await gh.wait_for_timeout(4000)
    await cs.stop()


async def merged(b):
    href = (ROOT / "pr.txt").read_text().strip()
    gh = await new_page(b, href)
    c = Cast(gh, "d_merged", fps=30)
    await c.start()
    event("merge_wait")
    for _ in range(180):  # up to ~12 min for a person to press Merge
        await gh.wait_for_timeout(4000)
        if await gh.locator("[data-status='pullMerged'], [title='Status: Merged'], span.State--merged").count():
            break
        await gh.reload(wait_until="domcontentloaded")
    event("merged_seen")
    await gh.wait_for_timeout(3000)
    await smooth_scroll(gh, 900, steps=50, pause=60)
    await gh.wait_for_timeout(3500)
    await c.stop()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True)
        if sys.argv[1:] == ["merged"]:
            await merged(b)
        else:
            await montage(b)
        await b.close()


asyncio.run(main())
