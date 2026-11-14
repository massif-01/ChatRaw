#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import sqlite3,pathlib,json
c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True);c.row_factory=sqlite3.Row
active=[dict(r) for r in c.execute("select id,chat_id,status from runs where status not in ('completed','failed','cancelled')")]
assert all(r['id']=='e05b8525931c4d1585cae79770c7be3d' and r['status']=='unknown' for r in active),active
p=pathlib.Path('/home/rm01/chatraw/deployment-e91d32f/compose.prebuilt.yml');old=p.read_text()
assert 'chatraw-agent-integration:e91d32f-amd64' in old
backup=p.with_name('compose.prebuilt.e91d32f.yml')
with backup.open('x') as f:f.write(old)
p.write_text(old.replace('chatraw-agent-integration:e91d32f-amd64','chatraw-agent-integration:2ba163e-ui'))
print(json.dumps({'remaining_nonterminal':active,'overlay_image':'chatraw-agent-integration:2ba163e-ui'}))
PY
cd /home/rm01/chatraw/deployment-e91d32f/ChatRaw-e91d32f
CHATRAW_RUNNER_TOKEN_FILE=/etc/chatraw-runner/token docker compose -p chatraw -f docker-compose.yml -f deploy/docker-compose.agent.yml -f ../compose.prebuilt.yml up -d --no-build --no-deps chatraw
docker inspect chatraw --format '{{.Id}} {{.Image}}'
