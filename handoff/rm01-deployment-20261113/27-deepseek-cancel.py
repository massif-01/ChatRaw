from api import api
import json,time,uuid,pathlib,subprocess
root=pathlib.Path(__file__).parent
cmd=['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99','/opt/chatraw-agents/hermes/source/.venv/bin/python /home/rm01/chatraw/deployment-e91d32f/observe-deepseek.py']
def native():return json.loads(subprocess.check_output(cmd,text=True))
before=native();start=time.time();chat='7660ee73-a125-49ed-9680-c9ab1b153b29'
run=api('POST','/api/agents/runs',{'chat_id':chat,'client_request_id':str(uuid.uuid4()),'message':'Do not use any tools. Output the integers from 1 to 5000, one integer per line, without abbreviation. This is a generation cancellation test. Begin immediately.','attachments':[]});rid=run['run_id']
for _ in range(45):
 dispatched=native()
 if len(dispatched['headers'])>len(before['headers']):break
 time.sleep(1)
else:raise RuntimeError('No new native request header observed')
time.sleep(3)
pre=api('GET',f'/api/agents/runs/{rid}');assert pre['status']=='running',pre
out={'agent':'deepseek','submitted':run,'native_before':before,'native_dispatched':dispatched,'before_cancel':pre,'first_content_observed':False,'cancel_mode':'process_stop','cancel_receipt':api('POST',f'/api/agents/runs/{rid}/cancel',{})}
for _ in range(35):
 snap=api('GET',f'/api/agents/runs/{rid}')
 if snap['status'] in ('completed','failed','cancelled','unknown'):break
 time.sleep(1)
out.update(after_cancel=snap,native_after=native(),elapsed=round(time.time()-start,2))
assert snap['status']=='cancelled',snap
old={(p['pid'],p['starttime_ticks']) for p in dispatched['native_processes']};new={(p['pid'],p['starttime_ticks']) for p in out['native_after']['native_processes']}
out['owned_runtime_exited']=bool(old) and not bool(old & new)
(root/'16-deepseek-cancel.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
