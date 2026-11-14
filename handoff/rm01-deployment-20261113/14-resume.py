from api import api
import json,time,sys,uuid,pathlib
root=pathlib.Path(__file__).parent
for agent in sys.argv[1:]:
 old=json.loads((root/f'07-{agent}.json').read_text());chat=old['chat_id']
 before=api('GET',f'/api/chats/{chat}/agent');started=time.time()
 run=api('POST','/api/agents/runs',{'chat_id':chat,'client_request_id':str(uuid.uuid4()),'message':'From our previous turn, repeat the literal RM99 validation marker and the working directory you actually observed. Use your existing conversation context only. Do not run any tools.','attachments':[]})
 out={'agent':agent,'before':before,'submitted':run};path=root/f'14-{agent}-resume.json';path.write_text(json.dumps(out,indent=2))
 for i in range(150):
  snap=api('GET',f"/api/agents/runs/{run['run_id']}")
  if snap['status'] not in ('running','queued'):break
  time.sleep(2)
 out.update(snapshot=snap,elapsed=round(time.time()-started,2),messages=api('GET',f'/api/chats/{chat}/messages'))
 path.write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='messages'}),flush=True)
 if snap['status']!='completed':break
