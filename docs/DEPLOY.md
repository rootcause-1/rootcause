# Deploying the public REPLAY demo

The public site runs RootCause in **replay mode**: FalkorDB + the API (`RC_MODE=replay`, autopilot agent) + the UI,
fed by the recordings in `replay/*.jsonl.gz` through the same ingest code as live mode. No OpenTelemetry Demo and
no Docker socket are needed; actions (flag reverts, restarts) are simulated and logged.

Any machine with Docker works:

```bash
git clone https://github.com/rootcause-1/rootcause && cd rootcause
RC_PUBLIC_PORT=80 docker compose -f infra/docker-compose.replay.yml up -d --build    # default port 8088
```

What a visitor sees: the healthy part of the recording is fast-forwarded on a virtual clock (baselines are warm
within seconds), then the broken part plays in real time and loops until someone approves the fix that matches the
recording (e.g. the `paymentFailure` flag revert). Then the recovery plays, and 2 minutes later the scenario starts
over on a fresh graph. Pick another scenario from the header, or reset: `POST /api/admin/reset`
(header `x-admin-token` if `RC_ADMIN_TOKEN` is set).

## Our host (AWS)

| | |
|---|---|
| URL | http://3.234.90.242/ |
| Instance | `i-017a66df01dba3925`, t4g.small (2 vCPU ARM, 2 GB), Amazon Linux 2023, 20 GB gp3, us-east-1 |
| Network | Elastic IP `3.234.90.242`, security group `rootcause-demo` (80 open, 22 from the team's IP only) |
| Cost | ~$12/month while running (tagged `project=rootcause`) |

Update after pushing to `main`: `scripts/deploy_aws.sh` (pulls `main` on the host and rebuilds the replay stack).

Host bootstrap (EC2 user-data):

```bash
dnf install -y docker git && systemctl enable --now docker && usermod -aG docker ec2-user
mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSL https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-aarch64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
curl -sSL https://github.com/docker/buildx/releases/download/v0.28.0/buildx-v0.28.0.linux-arm64 \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-*
```

Tear down after judging:

```bash
aws ec2 terminate-instances --instance-ids i-017a66df01dba3925
aws ec2 release-address --allocation-id $(aws ec2 describe-addresses --public-ips 3.234.90.242 --query 'Addresses[0].AllocationId' --output text)
```
