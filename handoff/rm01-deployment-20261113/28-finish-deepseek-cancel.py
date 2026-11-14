from api import api
import json,time,pathlib,subprocess
root=pathlib.Path(__file__).parent
ssh=['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99']
def native():return json.loads(subprocess.check_output(ssh+['/opt/chatraw-agents/hermes/source/.venv/bin/python /home/rm01/chatraw/deployment-e91d32f/observe-deepseek.py'],text=True))
rid='2ccbcb8956b841e2a6af805f0790e977';start=time.time();before=native();sockets=subprocess.check_output(ssh+['ss -tinp dst 10.10.99.98:58000'],text=True)
pre=api('GET',f'/api/agents/runs/{rid}');assert pre['status']=='running',pre
out={'agent':'deepseek','run_id':rid,'native_before_cancel':before,'outbound_socket_before_cancel':sockets,'before_cancel':pre,'first_content_observed':False,'cancel_mode':'process_stop','cancel_receipt':api('POST',f'/api/agents/runs/{rid}/cancel',{})}
p=root/'16-deepseek-cancel.json';p.write_text(json.dumps(out,indent=2))
for _ in range(40):
 snap=api('GET',f'/api/agents/runs/{rid}')
 if snap['status'] in ('completed','failed','cancelled','unknown'):break
 time.sleep(1)
out.update(after_cancel=snap,native_after=native(),cancel_elapsed=round(time.time()-start,2))
old={(p['pid'],p['starttime_ticks']) for p in before['native_processes']};new={(p['pid'],p['starttime_ticks']) for p in out['native_after']['native_processes']}
out['owned_runtime_exited']=bool(old) and not bool(old&new);p.write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
assert snap['status']=='cancelled' and out['owned_runtime_exited'],out
