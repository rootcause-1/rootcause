"""Phase E: re-film the FalkorDB Browser shots against the stored INC-0004 subgraph (alerts -> incident -> services,
the agent's Step trail, incident -> root cause -> PR -> code). Sets the query through Monaco's model (typing dropped
letters before) and checks the result node count before keeping the shot."""
import asyncio
import re

from playwright.async_api import async_playwright

from rec import Cast, event, fdb_open, new_page

QUERIES = [
    ("alerts", "MATCH (a:Alert)-[p:PART_OF]->(i:Incident) WHERE i.id = 'INC-0004' MATCH (a)-[f:FIRED_ON]->(s) RETURN a, p, i, f, s"),
    ("steps", "MATCH (i:Incident)-[x:INVESTIGATED_BY]->(st:Step) WHERE i.id = 'INC-0004' OPTIONAL MATCH (st)-[c:CITED]->(n) "
              "RETURN i, x, st, c, n"),
    ("pr", "MATCH (p:PullRequest)-[f:FIXES]->(i:Incident)-[rc:ROOT_CAUSE]->(r) OPTIONAL MATCH (p)-[c:CHANGES]->(m:CodeModule) "
           "OPTIONAL MATCH (m)-[im:IMPLEMENTS]->(s:Service) RETURN p, f, i, rc, r, c, m, im, s"),
]


async def set_query(page, text):
    await page.evaluate("(q) => navigator.clipboard.writeText(q)", text)
    ed = page.locator(".monaco-editor").first
    await ed.click()
    await page.keyboard.press("Meta+A")
    await page.keyboard.press("Meta+V")
    await page.wait_for_timeout(700)
    shown = await page.locator(".monaco-editor .view-lines").first.inner_text()
    return "paste", " ".join(shown.split())


async def nodes_count(page):
    txt = await page.evaluate("document.body.innerText")
    m = re.search(r"Nodes:\s*(\d+)", txt)
    return int(m.group(1)) if m else -1


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True)
        fdb = await new_page(b)
        await fdb.context.grant_permissions(["clipboard-read", "clipboard-write"], origin="http://localhost:3300")
        await fdb_open(fdb)
        before = await nodes_count(fdb)
        c = Cast(fdb, "e_fdb", fps=30)
        await c.start()
        for name, q in QUERIES:
            via_model, shown = await set_query(fdb, q)
            await fdb.wait_for_timeout(600)
            await fdb.keyboard.press("Escape")
            await fdb.locator("button.px-4.bg-primary").filter(has_text="RUN").first.click()
            event("fdb_shot", shot=name, via_model=via_model, shown=shown[:60])
            await fdb.wait_for_timeout(7000)
            event("fdb_result", shot=name, nodes=await nodes_count(fdb), before=before)
        await c.stop()
        await b.close()


asyncio.run(main())
