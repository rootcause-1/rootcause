"""Codebase scanner on a tiny synthetic repository (pure: files only, no git, no graph)."""

from __future__ import annotations

import pytest

from rootcause.codebase.repo import parse_url
from rootcause.codebase.scan import kebab, owners_for, scan


def _repo(tmp_path):
    (tmp_path / "compose.yaml").write_text("""
services:
  checkout:
    build: {context: ./, dockerfile: "${CHECKOUT_DOCKERFILE}"}
    depends_on: [payment, db]
    environment: [PAYMENT_ADDR, PRODUCT_CATALOG_ADDR=product-catalog:3550, OTEL_SERVICE_NAME=checkout]
  payment:
    build: {context: ./, dockerfile: ./src/payment/Dockerfile}
  product-catalog: {build: ./src/product-catalog}
  paymentTests: {build: {context: ./, dockerfile: ./src/payment/Dockerfile}}
  db: {image: postgres}
""", encoding="utf-8")
    for d in ("src/checkout", "src/payment", "src/product-catalog", "src/payment/test", "pb", ".github"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "src/checkout/main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    (tmp_path / "src/payment/charge.js").write_text("const a = 1;\nif (flag('paymentFailure')) fail();\n",
                                                   encoding="utf-8")
    (tmp_path / "src/payment/test/charge.test.js").write_text("flag('paymentFailure')\n", encoding="utf-8")
    (tmp_path / "pb/demo.proto").write_text(
        "service PaymentService {\n  rpc Charge(ChargeRequest) returns (ChargeResponse) {}\n}\n"
        "service ProductCatalogService {\n  rpc ListProducts(Empty) returns (L) {}\n  rpc GetProduct(G) returns (P) {}\n}\n",
        encoding="utf-8")
    (tmp_path / ".github/CODEOWNERS").write_text("* @org/all\n/src/payment/ @org/payments\n", encoding="utf-8")
    return tmp_path


def test_scan_finds_modules_declares_rpc_and_flag_reads(tmp_path):
    r = scan(_repo(tmp_path), ["paymentFailure", "cartFailure"])
    mods = {m["name"]: m for m in r["modules"]}
    assert mods["payment"]["path"] == "src/payment" and mods["payment"]["language"] == "JavaScript"
    assert mods["payment"]["owners"] == ["@org/payments"] and mods["checkout"]["owners"] == ["@org/all"]
    assert mods["paymentTests"]["path"] is None  # src/payment already belongs to payment
    assert mods["db"]["kind"] == "image"
    deps = {(d["src"], d["dst"], d["via"]) for d in r["declares"]}
    assert ("checkout", "payment", "depends_on") in deps and ("checkout", "db", "depends_on") in deps
    assert ("checkout", "product-catalog", "PRODUCT_CATALOG_ADDR") in deps
    assert not any(d["dst"] == "otel-service" for d in r["declares"])
    rpc = {x["name"]: x for x in r["rpc"]}
    assert rpc["ProductCatalogService"]["module"] == "product-catalog"
    assert rpc["ProductCatalogService"]["methods"] == ["ListProducts", "GetProduct"]
    # the test file mentioning the flag is ignored; the real read is found with its line
    assert r["flag_reads"] == [{"flag": "paymentFailure", "module": "payment", "file": "src/payment/charge.js",
                                "line": 2}]


def test_helpers():
    assert kebab("ProductCatalogService") == "product-catalog" and kebab("PAYMENT") == "payment"
    assert owners_for("src/payment", [("*", ["@a"]), ("/src/payment/", ["@b"])]) == ["@b"]
    assert parse_url("https://github.com/open-telemetry/opentelemetry-demo.git") == ("open-telemetry",
                                                                                      "opentelemetry-demo")
    for bad in ("http://github.com/a/b", "https://gitlab.com/a/b", "https://github.com/a", "file:///etc",
                "https://github.com/a/b;rm -rf /"):
        with pytest.raises(ValueError):
            parse_url(bad)
