#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import sqlite3,pathlib,hashlib
c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True)
rows=c.execute("select id,status from runs where status not in ('completed','failed','cancelled','interrupted')").fetchall()
assert all(row==('e05b8525931c4d1585cae79770c7be3d','unknown') for row in rows),rows
assert hashlib.sha256(pathlib.Path('/opt/chatraw-runner/agent_runner/adapters/codex.py').read_bytes()).hexdigest()=='a7d89c869f46a83d2f30fa88a2fd80a7b346773f1ae0776139edd88c9f569b2b'
assert hashlib.sha256(pathlib.Path('/home/rm01/chatraw/deployment-e91d32f/codex-e889688.py').read_bytes()).hexdigest()=='8778f84e49892f8a64dc78ffe95700b84132074b94fa2eae8d18c737beb0a972'
print('No real executing/waiting tasks; old and new Codex hashes verified')
PY
sudo -n systemctl stop chatraw-runner
sudo -n install -o root -g root -m 0644 /home/rm01/chatraw/deployment-e91d32f/codex-e889688.py /opt/chatraw-runner/agent_runner/adapters/codex.py
sudo -n systemctl start chatraw-runner
sudo -n systemctl is-active chatraw-runner
