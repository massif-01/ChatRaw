#!/usr/bin/env bash
set -euo pipefail
source_root=/home/rm01/chatraw/deployment-e91d32f/ChatRaw-e91d32f
sudo -n install -d -m 0755 /opt/chatraw-runner
sudo -n install -d -m 0750 -o root -g rm01 /etc/chatraw-runner
sudo -n install -d -m 0700 -o rm01 -g rm01 /var/lib/chatraw-runner /var/lib/chatraw-runner/pi-sessions /var/lib/chatraw-runner/deepseek /var/lib/chatraw-runner/codex-home /var/lib/chatraw-runner/claude-home /var/lib/chatraw-runner/pi-home /var/lib/chatraw-runner/hermes-home
sudo -n cp -R "$source_root/agent_runner" /opt/chatraw-runner/
sudo -n python3 -m venv --without-pip /opt/chatraw-runner/venv
sudo -n env UV_CACHE_DIR=/opt/chatraw-agents/cache/uv-runner /opt/chatraw-agents/tools/bin/uv pip install --python /opt/chatraw-runner/venv/bin/python -r "$source_root/agent_runner/requirements-claude.txt" -r "$source_root/agent_runner/requirements-deepseek.txt"
if [[ ! -e /etc/chatraw-runner/config.json ]]; then
 sudo -n install -m 0640 -o root -g rm01 "$source_root/deploy/runner-config.example.json" /etc/chatraw-runner/config.json
fi
sudo -n python3 - <<'PY'
import os,secrets,pwd
path='/etc/chatraw-runner/token'
if not os.path.exists(path):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as out:out.write(secrets.token_urlsafe(48)+'\n')
 user=pwd.getpwnam('rm01');os.chown(path,user.pw_uid,user.pw_gid)
PY
sed 's/@RUNNER_USER@/rm01/g' "$source_root/deploy/chatraw-runner.service" | sudo -n tee /etc/systemd/system/chatraw-runner.service >/dev/null
sudo -n chmod 0644 /etc/systemd/system/chatraw-runner.service
sudo -n systemctl daemon-reload
/opt/chatraw-runner/venv/bin/python - <<'PY'
from importlib.metadata import version
import json,platform
print(json.dumps({'python':platform.python_version(),'claude_sdk':version('claude-agent-sdk'),'deepseek_sdk':version('deepseek-harness-sdk'),'deepseek_runtime':version('deepseek-harness-runtime-bin')}))
PY
