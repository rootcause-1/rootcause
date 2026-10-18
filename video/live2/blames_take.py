"""Extra shot: FalkorDB Browser showing the BLAMES subgraph while a real paymentFailure incident is open.
Flips the flag in the demo's flag page, waits until FalkorDB holds >= 3 BLAMES edges, films the query, then
switches the flag back off (as the harness, not the agent)."""
import asyncio
import subprocess
import time

from playwright.async_api import async_playwright

import take
from take import Cast, event, fdb_open, fdb_query, new_page


def blames():
    out = subprocess.run(["docker", "exec", "rootcause-falkordb-1", "redis-cli", "GRAPH.RO_QUERY", "rc_live",
                          "MATCH (:Anomalous)-[b:BLAMES]->(:Anomalous) RETURN count(b)"], capture_output=True, text=True).stdout
    try:
        return int(out.split("\n")[1])
    except Exception:
        return 0


async def set_flag(b, value):
    flags = await new_page(b, "http://localhost:8080/feature")
    await flags.wait_for_timeout(2500)
    sel = flags.locator('select[name="paymentFailure"]')
    await sel.scroll_into_view_if_needed()
    await sel.select_option(value)
    event("flag_set", to=value)
    await flags.wait_for_timeout(2000)
    await flags.context.close()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True, args=["--force-device-scale-factor=1.25"])
        fdb = await new_page(b)
        await fdb_open(fdb)
        await set_flag(b, "100%")
        t0 = time.time()
        while blames() < 3 and time.time() - t0 < 240:
            await asyncio.sleep(2)
        event("blames_ready", count=blames())
        await asyncio.sleep(4)
        c = Cast(fdb, "fdb_blames2")
        await c.start()
        await fdb_query(fdb, "blames2", "MATCH (a:Anomalous)-[b:BLAMES]->(c:Anomalous) RETURN a, b, c", wait=10000)
        await c.stop()
        await set_flag(b, "off")
        await b.close()


if __name__ == "__main__":
    take.ROOT.mkdir(exist_ok=True)
    asyncio.run(main())
