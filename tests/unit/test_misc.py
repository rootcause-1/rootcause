"""Query registry rules, seed params, flag diffing, flagd edits, docker math, tool guards, replay segments."""

import gzip
import json
import re
from pathlib import Path

import pytest

from rootcause.actions.flagd import set_variant, with_variant
from rootcause.agent.loop import parse_verdict
from rootcause.graph.registry import QUERY_DIR, load_all, parse
from rootcause.graph.schema import seed_params
from rootcause.ingest.docker_stats import cpu_percent, slope_per_min
from rootcause.ingest.flag_watcher import actor_for, diff_flags, expect_change
from rootcause.replay.player import segments
from rootcause.settings import REPO_ROOT, get_settings
from rootcause.tools import FORBIDDEN

BACKEND = REPO_ROOT / "backend" / "rootcause"


def test_every_query_has_purpose_and_is_documented():
    queries = load_all()
    assert len(queries) > 40
    doc = (REPO_ROOT / "docs" / "QUERIES.md").read_text(encoding="utf-8")
    for name, nq in queries.items():
        assert nq.purpose, f"{name}.cypher needs a // purpose: line"
        assert nq.statements, name
        assert f"`{name}`" in doc, f"{name} missing from docs/QUERIES.md (run make queries-doc)"


def test_every_named_query_used_in_code_exists():
    names = set(load_all())
    used = set()
    for py in BACKEND.rglob("*.py"):
        if py.name == "client.py":  # its docstring shows run("name")
            continue
        used |= set(re.findall(r'\.(?:run|ro)\(\s*"([a-z_]+)"', py.read_text(encoding="utf-8")))
    assert used - names == set()


def test_no_inline_cypher_outside_schema_and_tools():
    allowed = {"schema.py", "client.py", "main.py", "registry.py"}  # bootstrap; raw(); seed check; keywords
    pattern = re.compile(r'"\s*(MATCH|MERGE|CREATE \(|CALL algo)')
    for py in BACKEND.rglob("*.py"):
        if py.name in allowed:
            continue
        assert not pattern.search(py.read_text(encoding="utf-8")), f"inline Cypher in {py}"


def test_registry_splits_statements():
    nq = parse("x", "// purpose: p\n// algorithm: algo.WCC\nMATCH (a) RETURN a\n;\nMATCH (b) RETURN b\n")
    assert nq.statements == ["MATCH (a) RETURN a", "MATCH (b) RETURN b"]
    assert nq.algorithm == "algo.WCC"
    assert QUERY_DIR.exists()


def test_seed_params_shape():
    p = seed_params(get_settings().seed)
    assert {t["id"] for t in p["teams"]} >= {"payments-team", "storefront-team", "platform-team", "data-team",
                                              "ai-team"}
    for t in p["teams"]:
        people = [x for x in p["people"] if x["team"] == t["id"]]
        assert len(people) == 2 and sum(x["on_call"] for x in people) == 1
    assert {j["id"] for j in p["journeys"]} == {"journey:browse", "journey:view_product", "journey:add_to_cart", "journey:checkout",
                                                "journey:ask_assistant"}


def test_flag_diff_and_actor():
    assert diff_flags(None, {"a": "off"}) == []
    assert diff_flags({"a": "off", "b": "on"}, {"a": "on", "b": "on"}) == [("a", "off", "on")]
    expect_change("a", "off")
    assert actor_for("a", "off") == "rootcause"
    assert actor_for("a", "off") == "unknown"  # single use


def test_flagd_atomic_write(tmp_path: Path):
    cfg = {"flags": {"paymentFailure": {"state": "ENABLED", "variants": {"off": 0, "100%": 1},
                                        "defaultVariant": "off"}}}
    f = tmp_path / "demo.flagd.json"
    f.write_text(json.dumps(cfg))
    out = set_variant(str(f), "paymentFailure", "100%", actor="harness")
    assert out == {"flag": "paymentFailure", "from": "off", "to": "100%"}
    assert json.loads(f.read_text())["flags"]["paymentFailure"]["defaultVariant"] == "100%"
    with pytest.raises(KeyError):
        with_variant(cfg, "paymentFailure", "nope")
    assert list(tmp_path.iterdir()) == [f]  # no temp files left behind


def test_docker_math():
    st = {"cpu_stats": {"cpu_usage": {"total_usage": 200}, "system_cpu_usage": 1000, "online_cpus": 2},
          "precpu_stats": {"cpu_usage": {"total_usage": 100}, "system_cpu_usage": 500}}
    assert cpu_percent(st) == pytest.approx(40.0)
    pts = [(i * 60_000, 100.0 + 10 * i) for i in range(4)]
    assert slope_per_min(pts) == pytest.approx(10.0)


def test_readonly_guard():
    assert FORBIDDEN.search("MATCH (n) DETACH DELETE n")
    assert FORBIDDEN.search("match (n) set n.x = 1")
    assert FORBIDDEN.search("CALL dbms.procedures()")
    assert not FORBIDDEN.search("MATCH (s:Service) RETURN s.id ORDER BY s.id SKIP 1 LIMIT 5")


def test_parse_verdict():
    assert parse_verdict('Done.\n{"root_cause": "payment", "confidence": 0.9}')["root_cause"] == "payment"
    assert parse_verdict("no json") is None


def test_replay_segments(tmp_path: Path):
    evs = [{"type": "marker", "ts": 0, "data": {"name": "start"}}, {"type": "otlp", "ts": 1, "data": {}},
           {"type": "marker", "ts": 2, "data": {"name": "break"}}, {"type": "otlp", "ts": 3, "data": {}},
           {"type": "marker", "ts": 4, "data": {"name": "fix", "kind": "flag_revert", "target": "paymentFailure"}},
           {"type": "otlp", "ts": 5, "data": {}}]
    p = tmp_path / "s.jsonl.gz"
    with gzip.open(p, "wt") as fh:
        fh.write("\n".join(json.dumps(e) for e in evs))
    seg = segments(evs)
    assert [len(seg[k]) for k in ("healthy", "broken", "recovery")] == [1, 1, 1]
    assert seg["fix"] == {"kind": "flag_revert", "target": "paymentFailure"}


def test_parse_body_gzip_json():
    import gzip
    import json

    from rootcause.ingest.otlp import parse_body

    doc = {"resourceSpans": []}
    raw = gzip.compress(json.dumps(doc).encode())
    assert parse_body(raw, "application/json", "gzip") == doc
    assert parse_body(raw, "application/json") == doc  # magic-byte sniffing
    assert parse_body(json.dumps(doc).encode(), "application/json") == doc
