import sys,json,subprocess,time,pathlib
from api import api
p=pathlib.Path(__file__).parent;r=json.loads((p/f'07-{sys.argv[1]}.json').read_text());rid=r['submitted']['run_id'];before=api('GET',f'/api/agents/runs/{rid}')
if before['status'] not in ('running','waiting_approval'): print('Skip active restart: run already terminal');raise SystemExit()
result=subprocess.run(['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99','docker restart chatraw'],capture_output=True,text=True,check=True)
for _ in range(20):
 try: after=api('GET',f'/api/agents/runs/{rid}');break
 except Exception:time.sleep(1)
record={'before':before,'after':after,'container_restart':result.stdout.strip()};(p/'10-chatraw-active-restart.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
