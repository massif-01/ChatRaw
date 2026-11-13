#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import sqlite3,pathlib,hashlib
c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True)
active=c.execute("select id,status from runs where status not in ('completed','failed','cancelled')").fetchall()
assert all(r==('e05b8525931c4d1585cae79770c7be3d','unknown') for r in active),active
base=pathlib.Path('/opt/chatraw-runner/agent_runner/adapters')
assert hashlib.sha256((base/'codex.py').read_bytes()).hexdigest()=='a7d89c869f46a83d2f30fa88a2fd80a7b346773f1ae0776139edd88c9f569b2b'
assert hashlib.sha256((base/'deepseek.py').read_bytes()).hexdigest()=='96e02e6e9ed421297fd5e90d32868831a625892e8874f923ca93932217905108'
assert hashlib.sha256(pathlib.Path('/home/rm01/chatraw/deployment-e91d32f/deepseek-99616b9.py').read_bytes()).hexdigest()=='60daa18d32f38d9999970f2a2a1b71e4b227193308ed14c49afb2c4873840391'
print('Gate passed: only preserved Codex unknown; exact old and new adapters verified')
PY
sudo -n systemctl stop chatraw-runner
sudo -n python3 - <<'PY'
import pathlib,json,os,grp
root=pathlib.Path('/etc/chatraw-runner');patch=root/'deepseek-rm01-models-v1.patch.yml';assert not patch.exists()
patch.write_text('- id: llm-deepseek\n  config:\n    models:\n      - id: RM-01 VLM\n        inputModalities: [text, image]\n        contextWindow: 262144\n');patch.chmod(0o440);os.chown(patch,0,grp.getgrnam('rm01').gr_gid)
p=root/'config.json';old=p.read_text();config=json.loads(old);assert 'patches' not in config['agents']['deepseek']
backup=root/'config.pre-deepseek-patches-v1.json'
with backup.open('x') as f:f.write(old)
backup.chmod(0o600)
config['agents']['deepseek']['patches']=[str(patch)];p.write_text(json.dumps(config,indent=2)+'\n')
print('Installed versioned read-only native model catalog; existing session rows untouched')
PY
sudo -n install -o root -g root -m 0644 /home/rm01/chatraw/deployment-e91d32f/deepseek-99616b9.py /opt/chatraw-runner/agent_runner/adapters/deepseek.py
sudo -n systemctl start chatraw-runner
sudo -n systemctl is-active chatraw-runner
