#!/usr/bin/env bash
# Pull-based deploy for the public replay host: if origin/main moved, rebuild and restart the replay stack.
# Installed as a systemd timer (rootcause-autodeploy.timer, every 2 min) by infra/autodeploy/install.sh.
# Pushing to main is the deploy; no inbound SSH needed.
set -euo pipefail
cd /home/ec2-user/rootcause
git fetch --quiet --depth 50 origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  git reset --quiet --hard origin/main
  RC_PUBLIC_PORT=80 docker compose -f infra/docker-compose.replay.yml up -d --build
  echo "deployed $(git rev-parse --short HEAD)"
fi
