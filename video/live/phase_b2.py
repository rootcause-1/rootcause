"""Rescue recorder for take 2: film from the fix prompt to the pull request (the take-2 script matched stale chat
text from an earlier incident and crashed before approving)."""
import asyncio

from playwright.async_api import async_playwright

from rec import ROOT, Cast, event, new_page, smooth_scroll
from phase_b import wait_text


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True)
        rc = await new_page(b, "http://localhost:8088/")
        await rc.wait_for_timeout(2500)
        c_rc = Cast(rc, "b2_rc", fps=25)
        await c_rc.start()
        btn = rc.locator("button", has_text="Yes, fix it")
        for _ in range(240):
            if await btn.count():
                break
            await rc.wait_for_timeout(500)
        if await btn.count():
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


asyncio.run(main())
