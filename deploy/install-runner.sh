#!/usr/bin/env bash
# Explicit host installation tool. It does not install/upgrade Agents or start services.
set -euo pipefail
if [[ $# != 1 || ! $1 =~ ^[a-z_][a-z0-9_-]*[$]?$ ]]; then
    echo "Usage: sudo bash deploy/install-runner.sh EXISTING_AGENT_ACCOUNT" >&2
    exit 2
fi
if [[ $(id -u) != 0 ]]; then
    echo "Installation needs root; service execution uses the selected existing account." >&2
    exit 2
fi
runner_user=$1
runner_group=$(id -gn "$runner_user")
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
install -d -m 0755 /opt/chatraw-runner
install -d -m 0700 -o "$runner_user" -g "$runner_group" /var/lib/chatraw-runner
install -d -m 0700 -o "$runner_user" -g "$runner_group" /var/lib/chatraw-runner/pi-sessions /var/lib/chatraw-runner/deepseek
install -d -m 0750 -o root -g "$runner_group" /etc/chatraw-runner
# Deployment is an explicit operator action; do not overwrite Agent home/config.
cp -R "$source_root/agent_runner" /opt/chatraw-runner/
python3 -m venv /opt/chatraw-runner/venv
/opt/chatraw-runner/venv/bin/python -m pip install -r /opt/chatraw-runner/agent_runner/requirements.txt
if [[ ! -e /etc/chatraw-runner/config.json ]]; then
    install -m 0640 -o root -g "$runner_group" "$source_root/deploy/runner-config.example.json" /etc/chatraw-runner/config.json
fi
if [[ ! -e /etc/chatraw-runner/token ]]; then
    (umask 077; python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > /etc/chatraw-runner/token)
    chown "$runner_user:$runner_group" /etc/chatraw-runner/token
fi
sed "s/@RUNNER_USER@/$runner_user/g" "$source_root/deploy/chatraw-runner.service" > /etc/systemd/system/chatraw-runner.service
chmod 0644 /etc/systemd/system/chatraw-runner.service
systemctl daemon-reload
echo "Installed Runner without starting it. Review /etc/chatraw-runner/config.json and native account configuration."
echo "Start during the approved deployment window: systemctl enable --now chatraw-runner"
