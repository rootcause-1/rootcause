"""The edit: which real footage plays under each voice line. Times are wall-clock IST from the 18 Oct recording.
Takes: a_* healthy phase; b_flags/b_shop/b_fdb/b_rc = take 2 (b_rc only for the map, its chat still showed the
previous incident); b2_rc = take 2 rescue (fresh page load: the INC-0004 story, fix, recovery, PR #2); b_gh = PR #2;
d_merged = PR #2 merged by Yash; c_* = feature montage. The live UI build was stale and labelled the writer "Claude"
(the backend used Gemini, see API logs and the PR text): those two chat lines are left out of frame."""
import datetime
import json
import time

from render import EVENTS, F_SANS, F_SERIF, GREEN, PINE, cast, t_of, text_frame

CHAT = (860, 484, 1060)        # bottom-right: the narrator chat (latest messages) + the right edge of the map
CHAT_HI = (860, 330, 1060)     # chat, higher up
MAP = (0, 110, 1400)           # the company map without the chat
CODE_PANEL = (840, 40, 1080)   # Codebase panel (right side)


def T(hms):
    return time.mktime(time.strptime(f"{datetime.date.today().isoformat()} {hms}", "%Y-%m-%d %H:%M:%S"))


def q(i):
    return [e for e in EVENTS if e["event"] == "fdb_query"][i]["t"]


def shot(name):
    return [e for e in EVENTS if e["event"] == "fdb_shot" and e.get("shot") == name][-1]["t"]


def build():
    S = []
    S.append({"key": "s01_hook", "clips": [
        {"cast": "b2_rc", "t0": T("14:35:07"), "t1": T("14:35:12"), "dur": 4.4,
         "overlays": [{"type": "title", "text": "RootCause",
                       "sub": "An AI on-call engineer that reads your system as a graph\nGraph Hacks 2026 · FalkorDB · Track 01"}]},
        {"cast": "b2_rc", "t0": T("14:35:20"), "t1": T("14:35:27"), "dur": 3.9, "zoom": [(0, MAP)],
         "overlays": [{"type": "live"}, {"type": "caption", "text": "Four alarms → one real cause: payment"}]},
        {"cast": "d_merged", "t0": t_of("merged_seen") + 0.5, "t1": t_of("merged_seen") + 4,
         "overlays": [{"type": "caption", "text": "…and the code fix, as a pull request a person merged"}]},
    ]})

    S.append({"key": "s02_build", "clips": [
        {"cast": "a_shop", "t0": cast("a_shop").t0, "t1": cast("a_shop").t1 + 1, "dur": 5.2,
         "overlays": [{"type": "live"}, {"type": "caption", "text": "The official OpenTelemetry Demo shop",
                                          "sub": "19 services · real traffic · on our laptop"}]},
        {"cast": "a_rc", "t0": t_of("reset") - 0.5, "t1": t_of("reset") + 40,
         "overlays": [{"type": "speed"}, {"type": "caption", "text": "RootCause builds the graph from live traces",
                                            "sub": "after a reset: one service, then all 19, every 5 seconds"}]},
    ]})

    S.append({"key": "s03_github", "clips": [
        {"cast": "a_rc", "t0": t_of("scan_click") - 5, "t1": t_of("scan_done") + 24,
         "zoom": [(0, CODE_PANEL), (0.28, (1160, 110, 760)), (0.62, (1160, 330, 760)), (1.0, (1160, 600, 760))],
         "overlays": [{"type": "speed"}, {"type": "caption", "text": "Connect GitHub: the fork is read into the graph",
                                            "sub": "modules · gRPC APIs · declared dependencies · flag reads · drift vs live traffic"}]},
    ]})

    S.append({"key": "s04_layers", "clips": [
        {"cast": "a_fdb", "t0": q(0) + 1, "t1": q(0) + 6, "dur": 2.4, "zoom": [(0, (420, 120, 1400))]},
        {"cast": "a_fdb", "t0": q(1) + 0.5, "t1": q(1) + 9.5, "zoom": [(0, (420, 120, 1400)), (1, (560, 170, 1200))],
         "overlays": [{"type": "caption", "text": "FalkorDB Browser: code modules → services → calls"}]},
    ]})

    resp = [e for e in EVENTS if e["event"] == "checkout_response"][-1]
    body = json.loads(resp["body"])
    S.append({"key": "s05_break", "clips": [
        {"cast": "b_flags", "t0": cast("b_flags").t0 + 1.0, "t1": cast("b_flags").t1 + 1.2, "dur": 4.4,
         "zoom": [(0, (0, 380, 1300)), (1, (60, 470, 1000))],
         "overlays": [{"type": "live"}, {"type": "caption", "text": "The bad change: paymentFailure → 100%",
                                          "sub": "made by hand in the demo's own flag page"}]},
        {"cast": "b_shop", "t0": cast("b_shop").t0, "t1": resp["t"] + 2.5,
         "overlays": [{"type": "caption", "text": f"Real response: POST /api/checkout → {resp['status']}",
                       "sub": f"\"{body.get('error', '')}\"  ({body.get('code', '')})", "from": 0.45}]},
    ]})

    S.append({"key": "s06_incident", "clips": [
        {"cast": "b_rc", "t0": T("14:32:22"), "t1": T("14:33:22"), "dur": 6.0, "zoom": [(0, MAP)],
         "overlays": [{"type": "live"}, {"type": "speed"}, {"type": "monitor", "box": (48, 700, 940, 1040), "from": 0.2}]},
        {"cast": "e_fdb", "t0": shot("alerts") + 1.5, "t1": shot("alerts") + 7.5, "dur": 4.0, "zoom": [(0, (300, 90, 1500))],
         "overlays": [{"type": "caption", "text": "In FalkorDB: 4 alerts, PART_OF one incident",
                       "sub": "each FIRED_ON the service it watches"}]},
        {"cast": "b2_rc", "t0": T("14:35:06"), "t1": T("14:35:19"), "dur": 5.0, "zoom": [(0, CHAT_HI), (1, CHAT)],
         "overlays": [{"type": "monitor", "box": (48, 640, 900, 1040)},
                      {"type": "caption", "text": "4 alarms → 1 incident · Gemini picks our MCP tools", "pos": "br"}]},
        {"cast": "e_fdb", "t0": shot("steps") + 1.5, "t1": shot("steps") + 7.5, "zoom": [(0, (300, 90, 1500))],
         "overlays": [{"type": "caption", "text": "Every tool call is a Step node, linked to the nodes it cited"}]},
    ]})

    S.append({"key": "s07_root", "clips": [
        {"cast": "b2_rc", "t0": T("14:35:19"), "t1": T("14:35:26"), "dur": 6.2, "zoom": [(0, (0, 0, 1920)), (1, MAP)],
         "overlays": [{"type": "caption", "text": "Root cause: payment · the evidence path through the graph"}]},
        {"cast": "b2_rc", "t0": T("14:35:26"), "t1": T("14:35:36"), "zoom": [(0, CHAT_HI), (1, CHAT)],
         "overlays": [{"type": "caption", "text": "The flag change, the code line, who hurts, who is on call"}]},
    ]})

    S.append({"key": "s08_fix", "clips": [
        {"cast": "b2_rc", "t0": T("14:35:36"), "t1": T("14:35:46"), "dur": 4.8, "zoom": [(0, CHAT)],
         "overlays": [{"type": "caption", "text": "Safest fix first · risk: low · a person approves"}]},
        {"cast": "b2_rc", "t0": T("14:35:46"), "t1": T("14:37:05"),
         "overlays": [{"type": "speed"}, {"type": "caption", "text": "Applied → all 4 alarms clear → verified (85 s)"}]},
    ]})

    gh0 = cast("b_gh").t0
    S.append({"key": "s09_pr", "dur": 23.0, "clips": [
        {"cast": "b2_rc", "t0": T("14:37:06"), "t1": T("14:37:13") + 0.4, "dur": 4.2, "zoom": [(0, CHAT)],
         "overlays": [{"type": "caption", "text": "Fix it in code? Yes, open a pull request"}]},
        {"cast": "b2_rc", "t0": T("14:37:40") + 0.6, "t1": T("14:37:48"), "dur": 3.4, "zoom": [(0, (1060, 430, 860))],
         "overlays": [{"type": "badge", "text": "Gemini wrote it in 27 s", "color": GREEN}]},
        {"cast": "b_gh", "t0": gh0 + 0.5, "t1": gh0 + 10, "dur": 5.6, "zoom": [(0, (120, 60, 1500)), (1, (120, 230, 1500))],
         "overlays": [{"type": "caption", "text": "PR #2 on GitHub, with the graph's evidence"}]},
        {"cast": "b_gh", "t0": gh0 + 13.5, "t1": cast("b_gh").t1, "dur": 5.0, "zoom": [(0, (100, 150, 1500)), (1, (200, 230, 1150))],
         "overlays": [{"type": "caption", "text": "One line in src/payment/charge.js, for a person to review"}]},
        {"cast": "d_merged", "t0": t_of("merged_seen") - 1, "t1": cast("d_merged").t1,
         "overlays": [{"type": "caption", "text": "Merged by a person. RootCause never merges itself."}]},
    ]})

    tabs = {}
    for e in EVENTS:
        if e["event"] == "tab":
            tabs[e["tab"]] = e["t"]
    S.append({"key": "s10_more", "clips": [
        {"cast": "c_rc", "t0": t_of("predict") - 1, "t1": t_of("predict") + 4.5, "dur": 3.4,
         "overlays": [{"type": "caption", "text": "Predict: what breaks if payment breaks"}]},
        {"cast": "c_rc", "t0": tabs["Memory"] + 0.5, "t1": tabs["Memory"] + 4.5, "dur": 2.8,
         "overlays": [{"type": "caption", "text": "Memory: past incidents and the fix that worked"}]},
        {"cast": "c_rc", "t0": tabs["Reports"] + 2.5, "t1": tabs["Reports"] + 8.5, "dur": 3.0,
         "overlays": [{"type": "caption", "text": "Reports, written from the graph"}]},
        {"cast": "c_rc", "t0": tabs["Your company"] + 0.5, "t1": tabs["Your company"] + 6.5,
         "overlays": [{"type": "caption", "text": "Your company: teams, on-call, runbooks, in the graph"}]},
    ]})

    end = text_frame([(120, "RootCause", PINE, F_SERIF),
                      (40, "Try it: http://3.234.90.242   ·   github.com/rootcause-1/rootcause", GREEN, F_SANS),
                      (32, "Graph Hacks 2026 · FalkorDB · Track 01: Agents That Act on Connected Data", PINE, F_SANS)])
    S.append({"key": "s11_proof", "clips": [
        {"cast": "e_fdb", "t0": shot("pr") + 1.5, "t1": shot("pr") + 7.5, "dur": 4.2, "zoom": [(0, (300, 90, 1500))],
         "overlays": [{"type": "caption", "text": "Incident → root cause → pull request → code module: one graph"}]},
        {"cast": "c_score", "t0": cast("c_score").t0, "t1": cast("c_score").t0 + 1.2, "dur": 6.8, "zoom": [(0, (330, 80, 1000)), (1, (360, 160, 900))],
         "overlays": [{"type": "caption", "text": "15 blind faults · scored by code, never typed",
                       "sub": "RootCause 80% · Gemini without the graph 80% · loudest alarm 53%"}]},
        {"kind": "still", "image": end},
    ]})
    return S


SCENES = build()
