#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import sqlite3
c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True)
rows=c.execute("select id,status from runs where status not in ('completed','failed','cancelled')").fetchall()
assert all(row==('e05b8525931c4d1585cae79770c7be3d','unknown') for row in rows),rows
print('No real executing/waiting tasks; existing unknown preserved')
PY
docker run --rm -i --network none --pull never --mount type=volume,src=chatraw_chatraw_data,dst=/app/data --entrypoint python chatraw-agent-integration:b5cafcd-icon - <<'PY'
import pathlib,hashlib,tempfile,os,stat,json
src=pathlib.Path('/app/Plugins/Plugin_market/hermes/icon.png');dst=pathlib.Path('/app/data/plugins/installed/hermes/icon.png');data=src.read_bytes()
assert hashlib.sha256(data).hexdigest()=='84dc1a015ab2055e774f1b0425e16d7f6a7611face26dfb186378f78f28b8d65'
assert hashlib.sha256(dst.read_bytes()).hexdigest()=='e441d6860d5e4621811dcb3a242ce37583d8b44d6fc7724fcf9cf0989069656e'
old=dst.stat()
with tempfile.NamedTemporaryFile(dir=dst.parent,prefix='.icon-',delete=False) as f:
 f.write(data);f.flush();os.fsync(f.fileno());tmp=pathlib.Path(f.name)
os.chmod(tmp,stat.S_IMODE(old.st_mode));os.chown(tmp,old.st_uid,old.st_gid);os.replace(tmp,dst)
print(json.dumps({'installed_icon_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'only_replaced':str(dst)}))
PY
python3 - <<'PY'
from pathlib import Path
p=Path('/home/rm01/chatraw/deployment-e91d32f/compose.prebuilt.yml');old=p.read_text();assert 'chatraw-agent-integration:2ba163e-ui' in old
with p.with_name('compose.prebuilt.2ba163e-ui.yml').open('x') as f:f.write(old)
p.write_text(old.replace('chatraw-agent-integration:2ba163e-ui','chatraw-agent-integration:b5cafcd-icon'))
PY
cd /home/rm01/chatraw/deployment-e91d32f/ChatRaw-e91d32f
CHATRAW_RUNNER_TOKEN_FILE=/etc/chatraw-runner/token docker compose -p chatraw -f docker-compose.yml -f deploy/docker-compose.agent.yml -f ../compose.prebuilt.yml up -d --no-build --no-deps chatraw
docker inspect chatraw --format '{{.Id}} {{.Image}}'
