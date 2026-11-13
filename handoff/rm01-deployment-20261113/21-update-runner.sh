#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import sqlite3,hashlib,pathlib,ast,json
c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True)
assert c.execute("select count(*) from runs where status not in ('completed','failed','cancelled')").fetchone()[0]==0
old=pathlib.Path('/opt/chatraw-runner/agent_runner/adapters/deepseek.py').read_bytes()
new=pathlib.Path('/home/rm01/chatraw/deployment-e91d32f/deepseek-bec078b.py').read_bytes()
assert hashlib.sha256(old).hexdigest()=='91cf50cca8cfa90dcac11e2c1ca6f0730f59133c472c806d396b1baad49817b2'
assert hashlib.sha256(new).hexdigest()=='96e02e6e9ed421297fd5e90d32868831a625892e8874f923ca93932217905108'
ast.parse(new)
print(json.dumps({'nonterminal_runs':0,'old_and_new_hashes_verified':True}))
PY
sudo -n systemctl stop chatraw-runner
sudo -n install -o root -g root -m 0644 /home/rm01/chatraw/deployment-e91d32f/deepseek-bec078b.py /opt/chatraw-runner/agent_runner/adapters/deepseek.py
sudo -n systemctl start chatraw-runner
sudo -n systemctl is-active chatraw-runner
sha256sum /opt/chatraw-runner/agent_runner/adapters/deepseek.py
