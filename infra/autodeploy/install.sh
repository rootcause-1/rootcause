#!/usr/bin/env bash
# Run once on the replay host (as ec2-user, with sudo): installs the 2-minute pull-and-redeploy timer.
set -euo pipefail
sudo tee /etc/systemd/system/rootcause-autodeploy.service >/dev/null <<'EOF'
[Unit]
Description=RootCause replay: redeploy when origin/main changes
After=docker.service network-online.target

[Service]
Type=oneshot
User=ec2-user
ExecStart=/bin/bash /home/ec2-user/rootcause/infra/autodeploy/rootcause-autodeploy.sh
EOF
sudo tee /etc/systemd/system/rootcause-autodeploy.timer >/dev/null <<'EOF'
[Unit]
Description=Check for RootCause updates every 2 minutes

[Timer]
OnBootSec=60
OnUnitActiveSec=120

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now rootcause-autodeploy.timer
systemctl list-timers rootcause-autodeploy.timer --no-pager
