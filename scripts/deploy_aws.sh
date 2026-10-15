#!/usr/bin/env bash
# Deploy (or update) the public REPLAY demo on the AWS host: pull main from GitHub, rebuild, restart.
# Usage: scripts/deploy_aws.sh [host] [ssh-key]
# Defaults: the team's demo host (t4g.small, us-east-1, Elastic IP) and ~/.ssh/rootcause-demo.pem.
# The host only needs docker + compose + git (see the user-data in docs/DEPLOY.md). Serves the UI on port 80.
set -euo pipefail
HOST="${1:-${RC_DEMO_HOST:-3.234.90.242}}"
KEY="${2:-${RC_DEMO_KEY:-$HOME/.ssh/rootcause-demo.pem}}"
REPO="https://github.com/rootcause-1/rootcause.git"

# port 22 is occasionally flaky from some networks: retry the connection a few times
for i in 1 2 3 4 5; do ssh -i "$KEY" -o ConnectTimeout=20 "ec2-user@$HOST" true && break; echo "ssh retry $i"; sleep 5; done
ssh -i "$KEY" -o ConnectTimeout=20 "ec2-user@$HOST" bash -s <<EOF
set -euo pipefail
[ -d rootcause/.git ] || git clone --depth 50 "$REPO" rootcause
cd rootcause
git fetch --depth 50 origin main && git reset --hard origin/main
RC_PUBLIC_PORT=80 docker compose -f infra/docker-compose.replay.yml up -d --build
docker compose -f infra/docker-compose.replay.yml ps
EOF
echo "deployed: http://$HOST/"
