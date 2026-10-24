#!/usr/bin/env bash
# Installs the yWorkspace server agent with a systemd timer (every 5 minutes). Run on the server as root.
set -euo pipefail
install -m 755 yw_agent.py /usr/local/bin/yw-agent
[ -f /etc/yw-agent.json ] || install -m 600 yw-agent.json /etc/yw-agent.json
cat > /etc/systemd/system/yw-agent.service <<UNIT
[Unit]
Description=yWorkspace monitoring agent (local only, sends nothing)
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/bin/yw-agent /etc/yw-agent.json
UNIT
cat > /etc/systemd/system/yw-agent.timer <<UNIT
[Unit]
Description=Run the yWorkspace agent every 5 minutes
[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now yw-agent.timer
echo "yw-agent installed. Status file: /var/lib/yw-agent/status.json"
