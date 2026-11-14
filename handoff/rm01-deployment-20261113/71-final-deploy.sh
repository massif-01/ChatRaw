#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import sqlite3,pathlib,hashlib,json
c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True)
rows=c.execute("select id,status from runs where status not in ('completed','failed','cancelled','interrupted')").fetchall();assert all(r==('e05b8525931c4d1585cae79770c7be3d','unknown') for r in rows),rows
root=pathlib.Path('/home/rm01/chatraw/final-adeb279/runner');m=json.loads((root/'runtime-manifest.json').read_text())
for name in ('codex.py','codex_responses.py','deepseek.py'):assert hashlib.sha256((root/name).read_bytes()).hexdigest()==m['agent_runner/adapters/'+name]
print('Final maintenance gate and pinned source hashes passed')
PY
docker stop chatraw
sudo -n systemctl stop chatraw-runner
if ! sudo -n python3 /home/rm01/chatraw/final-adeb279/maintenance-backup.py > /home/rm01/chatraw/final-adeb279/maintenance-backup-result.json; then
  sudo -n systemctl start chatraw-runner
  docker start chatraw
  exit 1
fi
for name in codex.py codex_responses.py deepseek.py; do
  sudo -n install -o root -g root -m 0644 "/home/rm01/chatraw/final-adeb279/runner/$name" "/opt/chatraw-runner/agent_runner/adapters/$name"
done
sudo -n python3 - <<'PY'
import pathlib,json
p=pathlib.Path('/etc/chatraw-runner/config.json');old=p.read_text();config=json.loads(old);assert 'responses_compat_upstream' not in config['agents'].get('codex',{})
backup=p.with_name('config.pre-final-adeb279.json')
with backup.open('x') as f:f.write(old)
backup.chmod(0o600)
config['agents'].setdefault('codex',{})['responses_compat_upstream']='http://10.10.99.98:58000/v1/responses';p.write_text(json.dumps(config,indent=2)+'\n')
PY
python3 - <<'PY'
from pathlib import Path
p=Path('/home/rm01/chatraw/deployment-e91d32f/compose.prebuilt.yml');old=p.read_text();assert 'chatraw-agent-integration:b5cafcd-icon' in old
with p.with_name('compose.prebuilt.b5cafcd-icon.yml').open('x') as f:f.write(old)
p.write_text(old.replace('chatraw-agent-integration:b5cafcd-icon','chatraw-agent-integration:adeb279-final-ui'))
PY
sudo -n systemctl start chatraw-runner
cd /home/rm01/chatraw/deployment-e91d32f/ChatRaw-e91d32f
CHATRAW_RUNNER_TOKEN_FILE=/etc/chatraw-runner/token docker compose -p chatraw -f docker-compose.yml -f deploy/docker-compose.agent.yml -f ../compose.prebuilt.yml up -d --no-build --no-deps chatraw
sudo -n systemctl is-active chatraw-runner chatraw-hermes
docker inspect chatraw --format '{{.Id}} {{.Image}}'
