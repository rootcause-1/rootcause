#!/usr/bin/env bash
# Clone the OpenTelemetry Demo next to this repo, install our collector override, start it in agentic mode.
set -euo pipefail
cd "$(dirname "$0")/.."
DEMO="${DEMO_REPO_PATH:-../opentelemetry-demo}"

if [ ! -d "$DEMO/.git" ]; then
  git clone --depth 1 https://github.com/open-telemetry/opentelemetry-demo "$DEMO"
fi

cp infra/otelcol-config-extras.yml "$DEMO/src/otel-collector/otelcol-config-extras.yml"
echo "installed collector override -> $DEMO/src/otel-collector/otelcol-config-extras.yml"

# our API must exist on the demo network before the collector exports to it; the exporter retries until then
(cd "$DEMO" && make start-agentic)

cat <<'EOF'

Demo starting (agentic mode). Next:
  1. docker network ls            -> VERIFY the network name, set demo.network in config/rootcause.yaml
  2. docker compose -f ... logs otel-collector | grep -i rootcause  -> VERIFY exporter accepted (no config errors)
  3. make up && make seed
  4. python scripts/discover_metrics.py  -> fill prometheus.queries in config/rootcause.yaml
EOF
