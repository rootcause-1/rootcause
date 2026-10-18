"""The edit: which footage plays under each narration beat. Live clips play at 1x unless a real wait has to be
compressed; then the speed badge says so. `at` = the sentence index where a clip starts (sync to the voice)."""
from render2 import EVENTS, ev

E = lambda name, **kw: ev(name, **kw)


def q(shot):
    return ev("fdb_query", shot=shot)


def build():
    S = [{"key": "intro", "kind": "mg"}, {"key": "title", "kind": "mg"}, {"key": "pipeline", "kind": "mg"}]
    have = {e["event"] for e in EVENTS}
    reset = E("reset")
    if not reset:
        return S + [{"key": "end", "kind": "mg"}]
    from render2 import cast
    sh = cast("shop_healthy")
    S += [
        {"key": "shop", "kind": "live", "chapter": "Live demo · the shop", "clips": [
            {"cast": "shop_healthy", "t0": sh.ts[0] + 1.0, "speed": 1.0,
             "caption": "The official OpenTelemetry Demo", "sub": "a real shop on our laptop · live traffic from a load generator"}]},
        {"key": "build", "kind": "live", "chapter": "Live demo · the graph builds itself", "min_dur": 18, "clips": [
            {"cast": "rc", "t0": reset + 4.3, "speed": 1.0,
             "caption": "Building the graph from live traces", "sub": "after a reset · real time"}]},
        {"key": "github", "kind": "live", "chapter": "Live demo · connect GitHub", "clips": [
            {"cast": "rc", "t0": E("codebase_open") + 0.5, "t1": E("scan_click") + 1.0,
             "caption": "Connect your GitHub"},
            {"at": 1, "cast": "rc", "t0": E("scan_done"), "t1": E("drift_view") - 4,
             "caption": "The code goes into the same graph", "sub": "modules · APIs · flag reads with file and line"},
            {"at": 2, "cast": "rc", "t0": E("drift_view") - 3, "t1": E("codebase_close") - 0.5,
             "caption": "Drift: code vs live traffic"}]},
        {"key": "layers", "kind": "live", "chapter": "Inside FalkorDB", "min_dur": 9, "clips": [
            {"cast": "fdb_layers", "t0": q("calls") + 1.0, "t1": q("calls") + 8.5, "caption": "FalkorDB Browser: services and calls"},
            {"frac": 0.42, "cast": "fdb_layers", "t0": q("code") + 1.0, "t1": q("code") + 9.5,
             "caption": "…and the code layer on top"}]},
    ]
    if "checkout_response" in have:
        import json
        r = [e for e in EVENTS if e["event"] == "checkout_response"][-1]
        body = json.loads(r["body"]) if str(r["body"]).startswith("{") else {}
        fl = cast("flags")
        S.append({"key": "break", "kind": "live", "chapter": "Live demo · something breaks", "min_dur": 13, "clips": [
            {"cast": "flags", "t0": fl.ts[0] + 0.5, "speed": 1.0, "caption": "The demo's own flag page",
             "sub": "paymentFailure → 100%"},
            {"at": 2, "cast": "shop_fail", "t0": cast("shop_fail").ts[0] + 1.0, "t1": r["t"] + 2.5,
             "pre_caption": "A customer tries to pay", "caption_after": r["t"] - 0.3,
             "caption": f"Checkout → {r['status']} {body.get('code', '')}", "sub": body.get("error", "")}]})
    if "fix_prompt" in have:
        S += [
            {"key": "alarms", "kind": "live", "chapter": "Live demo · the incident", "min_dur": 13, "clips": [
                {"cast": "rc", "t0": E("alarms") - 6, "t1": E("incident") + 9, "caption": "Alarms → one incident"}]},
            {"key": "blames", "kind": "live", "chapter": "Inside FalkorDB · mid-incident", "min_dur": 9, "clips": [
                {"cast": "fdb_blames2", "t0": q("blames2") + 0.8, "t1": q("blames2") + 9.5,
                 "caption": "BLAMES edges between the failing services", "sub": "connected components → one incident"}]},
            {"key": "investigate", "kind": "live", "chapter": "Live demo · Gemini investigates", "min_dur": 20, "clips": [
                {"cast": "rc", "t0": E("investigating") - 1, "t1": E("root_cause") - 1, "caption": "Gemini picks our MCP tools",
                 "sub": "every tool call is a query on the FalkorDB graph"}]},
            {"key": "root", "kind": "live", "chapter": "Live demo · root cause", "min_dur": 16, "clips": [
                {"cast": "rc", "t0": E("root_cause") - 1, "t1": E("fix_prompt") - 1, "caption": "Root cause, with proof"}]},
            {"key": "fix", "kind": "live", "chapter": "Live demo · the fix", "clips": [
                {"cast": "rc", "t0": E("fix_prompt") - 1, "t1": E("approve_fix") + 2.5, "caption": "Safest fix first · you approve"}]},
            {"key": "recover", "kind": "live", "chapter": "Live demo · verify", "min_dur": 14, "clips": [
                {"cast": "rc", "t0": E("approve_fix") + 2.5, "t1": E("recovered") + 3, "caption": "Watching every alarm clear"}]},
        ]
    if "pr_open" in have:
        S.append({"key": "pr", "kind": "live", "chapter": "Live demo · fix it in code", "min_dur": 9, "clips": [
            {"cast": "rc", "t0": E("pr_offer") - 1, "t1": E("pr_offer") + 6, "caption": "Fix it in code?"},
            {"frac": 0.3, "cast": "rc", "t0": E("approve_pr") - 1.5, "t1": E("approve_pr") + 4, "caption": "Yes, open a pull request"},
            {"at": 1, "cast": "rc", "t0": E("pr_open") - 4, "t1": E("pr_open") + 6, "caption": "Gemini writes the change"}]})
    if "merged_seen" in have:
        g = cast("github")
        S += [
            {"key": "github_pr", "kind": "live", "chapter": "Live demo · the pull request", "min_dur": 14, "spread": True, "clips": [
                {"say": [0], "cast": "github", "t0": g.ts[0] + 1.0, "t1": E("gh_files") - 0.5, "caption": "A real pull request on GitHub",
                 "sub": "root cause · evidence path · change · impact"},
                {"say": [1, 2], "frac": 0.5, "cast": "github", "t0": E("gh_files") + 2.0, "t1": E("gh_files") + 11, "caption": "The one-line change"}]},
            {"key": "merge", "kind": "live", "chapter": "Live demo · a person merges", "min_dur": 6, "clips": [
                {"cast": "github", "t0": E("merged_seen") - 1, "t1": E("merged_seen") + 6, "caption": "Merged by a person"}]},
        ]
    if "done" in have:
        S += [
            {"key": "onegraph", "kind": "live", "chapter": "Inside FalkorDB · one graph", "min_dur": 13.5, "spread": True, "clips": [
                {"say": [0], "cast": "fdb_final", "t0": q("alerts") + 1.0, "t1": q("alerts") + 7.5, "caption": "Alerts PART_OF the incident"},
                {"say": [1], "cast": "fdb_final", "t0": q("steps") + 1.0, "t1": q("steps") + 7.5, "caption": "Every agent step, and what it cited"},
                {"say": [2], "cast": "fdb_final", "t0": q("pr") + 1.0, "t1": q("pr") + 7.5, "caption": "Incident → PR → code module"}]},
            {"key": "tabs", "kind": "live", "chapter": "More features", "min_dur": 16, "spread": True, "clips": [
                {"say": [0], "cast": "tabs", "t0": E("tab", tab="Predict") - 3.5, "t1": E("tab", tab="Memory"), "caption": "Predict"},
                {"say": [1], "cast": "tabs", "t0": E("tab", tab="Memory"), "t1": E("tab", tab="Reports"), "caption": "Memory"},
                {"say": [2], "cast": "tabs", "t0": E("tab", tab="Reports") + 2, "t1": E("tab", tab="Your company"), "caption": "Reports"},
                {"say": [3], "cast": "tabs", "t0": E("tab", tab="Your company"), "t1": E("tab", tab="Break something"),
                 "caption": "Your company"}]},
            {"key": "score", "kind": "live", "chapter": "Proof", "min_dur": 10, "clips": [
                {"cast": "scorecard", "t0": cast("scorecard").ts[0], "t1": cast("scorecard").ts[-1],
                 "caption": "15 blind faults · scored by code, never typed"}]},
        ]
    return S + [{"key": "end", "kind": "mg"}]


SEGMENTS = build()
