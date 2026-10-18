"""Settings: environment variables (pydantic-settings) merged with config/rootcause.yaml and config/seed.yaml.

Uses no graph queries. Every other module reads configuration through `get_settings()`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(os.environ.get("RC_CONFIG_DIR", REPO_ROOT / "config"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    falkordb_host: str = "localhost"
    falkordb_port: int = 6380
    rc_graph: str = "rc_live"
    rc_mode: str = "live"  # live | replay
    rc_tick_seconds: float = 5.0
    rc_window_seconds: int = 60
    prometheus_url: str | None = None
    demo_repo_path: str = "../opentelemetry-demo"
    flagd_config_path: str | None = None
    gemini_api_key: str = ""
    rc_llm_model: str = "gemini-2.5-flash"
    rc_agent_mode: str = "autopilot"  # autopilot | llm
    pager_webhook_url: str = ""
    github_token: str = ""  # fix-it-in-code PRs on code.pr_repo only
    rc_api_url: str = "http://localhost:8000"
    rc_mcp_url: str = "http://localhost:8811/mcp"
    rc_replay_scenario: str = ""
    rc_data_dir: str = str(REPO_ROOT / "data")
    rc_reports_dir: str = str(REPO_ROOT / "reports")
    rc_replay_dir: str = str(REPO_ROOT / "replay")
    rc_docs_dir: str = str(REPO_ROOT / "docs")

    # loaded from yaml (not env)
    cfg: dict[str, Any] = {}
    seed: dict[str, Any] = {}

    def c(self, *path: str, default: Any = None) -> Any:
        """Read a nested value from rootcause.yaml: settings.c('detect', 'hold_ticks')."""
        node: Any = self.cfg
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return default if node is None else node

    @property
    def flagd_path(self) -> str | None:
        if self.flagd_config_path:
            return os.path.expandvars(self.flagd_config_path.replace("${DEMO_REPO_PATH}", self.demo_repo_path))
        return self.c("flagd", "path")

    @property
    def prom_url(self) -> str | None:
        return self.prometheus_url or self.c("prometheus", "url")

    @property
    def non_candidates(self) -> set[str]:
        return set(self.c("non_candidates", default=[]))


def _load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.cfg = _load_yaml("rootcause.yaml")
    s.seed = _load_yaml("seed.yaml")
    return s
