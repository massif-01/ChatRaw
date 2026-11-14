#!/usr/bin/env bash
set -euo pipefail
stage=/home/rm01/chatraw/deployment-e91d32f
cd "$stage"
sha256sum -c SHA256SUMS
if [[ ! -d ChatRaw-e91d32f ]]; then tar -xzf ChatRaw-e91d32f.tar.gz; fi
expected_image=sha256:faeb75dc86eb10583fa0af6a800e3c630247e2a193d7c7f2cd232d48162a45a9
installed_image=$(docker image inspect chatraw-agent-integration:e91d32f-amd64 --format '{{.Id}}' 2>/dev/null || true)
if [[ "$installed_image" != "$expected_image" ]]; then docker load -i ChatRaw-e91d32f-linux-amd64.docker.tar.gz; fi
test "$(docker image inspect chatraw-agent-integration:e91d32f-amd64 --format '{{.Id}}')" = "$expected_image"
cd ChatRaw-e91d32f
sudo -n bash deploy/install-runner.sh rm01
sudo -n /opt/chatraw-runner/venv/bin/python -m pip install -r agent_runner/requirements-claude.txt -r agent_runner/requirements-deepseek.txt
sudo -n install -d -m 0755 -o rm01 -g rm01 /opt/chatraw-agents /opt/chatraw-agents/codex /opt/chatraw-agents/pi /opt/chatraw-agents/hermes /opt/chatraw-agents/bin /opt/chatraw-agents/cache /opt/chatraw-agents/python
sudo -n install -d -m 0700 -o rm01 -g rm01 /var/lib/chatraw-runner/codex-home /var/lib/chatraw-runner/claude-home /var/lib/chatraw-runner/pi-home /var/lib/chatraw-runner/hermes-home
/opt/chatraw-runner/venv/bin/python - <<'PY'
from importlib.metadata import version
import json,platform
print(json.dumps({'python':platform.python_version(),'claude_sdk':version('claude-agent-sdk'),'deepseek_sdk':version('deepseek-harness-sdk'),'deepseek_runtime':version('deepseek-harness-runtime-bin')}))
PY
