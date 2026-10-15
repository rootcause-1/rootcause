"""FalkorDB for graph tests: a testcontainers FalkorDB per session, or FALKORDB_TEST_HOST/PORT if set.
Never mocked. Tests skip (not fail) when neither Docker nor a test host is available."""

from __future__ import annotations

import os
import uuid

import pytest
from falkordb.asyncio import FalkorDB

from rootcause.graph.client import GraphDB
from rootcause.graph.schema import ensure_indexes, load_seed
from rootcause.settings import get_settings


@pytest.fixture(scope="session")
def falkor_addr():
    if os.environ.get("FALKORDB_TEST_HOST"):
        yield os.environ["FALKORDB_TEST_HOST"], int(os.environ.get("FALKORDB_TEST_PORT", 6379))
        return
    try:
        from testcontainers.core.container import DockerContainer
        from testcontainers.core.waiting_utils import wait_for_logs

        c = DockerContainer("falkordb/falkordb:latest").with_exposed_ports(6379)
        c.start()
    except Exception as exc:  # no docker on this machine
        pytest.skip(f"FalkorDB test container unavailable: {exc}")
    wait_for_logs(c, "Ready to accept connections", timeout=60)
    yield c.get_container_host_ip(), int(c.get_exposed_port(6379))
    c.stop()


@pytest.fixture
async def db(falkor_addr):
    host, port = falkor_addr
    g = GraphDB(f"rc_eval_test_{uuid.uuid4().hex[:8]}", FalkorDB(host=host, port=port))
    await ensure_indexes(g)
    await load_seed(g, get_settings().seed)
    yield g
    await g.delete()
