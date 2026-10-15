"""Restart the container of a demo service with the Docker SDK (mounted /var/run/docker.sock).

No graph queries: docker events turn the restart into a (:Change {kind:'restart', actor:'rootcause'}).
"""

from __future__ import annotations

import asyncio

from rootcause.ingest.pipeline import expect_restart
from rootcause.util import now_ms


def _restart(project: str, service: str) -> str:
    import docker

    client = docker.from_env()
    found = client.containers.list(all=True, filters={"label": [
        f"com.docker.compose.project={project}", f"com.docker.compose.service={service}"]})
    if not found:
        raise LookupError(f"no container for service {service} in project {project}")
    c = found[0]
    expect_restart(c.name, now_ms() + 120_000)
    c.restart(timeout=10)
    return c.name


async def restart(project: str, service: str) -> dict[str, str]:
    name = await asyncio.to_thread(_restart, project, service)
    return {"service": service, "container": name}
