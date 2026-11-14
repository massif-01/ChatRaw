#!/usr/bin/env bash
set -euo pipefail
sudo -n install -d -m 0755 -o rm01 -g rm01 /opt/chatraw-agents /opt/chatraw-agents/codex /opt/chatraw-agents/pi /opt/chatraw-agents/hermes /opt/chatraw-agents/bin /opt/chatraw-agents/cache /opt/chatraw-agents/python
npm install --prefix /opt/chatraw-agents/codex --no-audit --no-fund @openai/codex@0.153.4
npm install --prefix /opt/chatraw-agents/pi --no-audit --no-fund @earendil-works/pi-coding-agent@1.5.2
/opt/chatraw-agents/codex/node_modules/.bin/codex --version
/opt/chatraw-agents/pi/node_modules/.bin/pi --version
