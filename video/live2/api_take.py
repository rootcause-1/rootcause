"""Extra shots: the API layer in FalkorDB Browser (gRPC services and who serves them, declared dependencies,
and calls seen in live traffic that the code never declares)."""
import asyncio

from playwright.async_api import async_playwright

from take import Cast, fdb_open, fdb_query, new_page

SHOTS = [
    ("api", "MATCH (m:CodeModule)-[s:SERVES]->(r:RpcService) RETURN m, s, r"),
    ("deps", "MATCH (a:CodeModule)-[d:DECLARES]->(b:CodeModule) RETURN a, d, b"),
    ("drift", "MATCH (ma:CodeModule)-[:IMPLEMENTS]->(a:Service)-[c:CALLS]->(b:Service)<-[:IMPLEMENTS]-(mb:CodeModule) "
              "WHERE NOT (ma)-[:DECLARES]->(mb) RETURN a, c, b"),
]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True, args=["--force-device-scale-factor=1.25"])
        fdb = await new_page(b)
        await fdb_open(fdb)
        c = Cast(fdb, "fdb_api")
        await c.start()
        for name, q in SHOTS:
            await fdb_query(fdb, name, q, wait=9000)
        await c.stop()
        await b.close()


asyncio.run(main())
