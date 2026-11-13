from api import api
import json,time,sys,uuid,pathlib
agent=sys.argv[1]
path=pathlib.Path(__file__).parent/f'07-{agent}.json'
if path.exists():
 record=json.loads(path.read_text());run=record['submitted']
else:
 record={'agent':agent,'started_at':time.time()}
 chat=api('POST','/api/chats'); record['chat_id']=chat['id']
 record['binding']=api('PUT',f"/api/chats/{chat['id']}/agent",{'agent_id':agent,'workspace':{'kind':'managed'}})
 run=api('POST','/api/agents/runs',{'chat_id':chat['id'],'client_request_id':str(uuid.uuid4()),'message':'Use your native shell/terminal tool to run pwd exactly once. Then reply with the working directory and the literal text RM99_NATIVE_OK. Do not access other files or make network requests.','attachments':[]})
 record['submitted']=run
 path=pathlib.Path(__file__).parent/f'07-{agent}.json'
 path.write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
for i in range(360):
 snap=api('GET',f"/api/agents/runs/{run['run_id']}")
 record['snapshot']=snap;record['elapsed']=round(time.time()-record['started_at'],2)
 path.write_text(json.dumps(record,indent=2))
 status=snap.get('status'); print(json.dumps({'agent':agent,'elapsed':record['elapsed'],'status':status,'snapshot':snap if status not in ('running','queued') else None}),flush=True)
 if status in ('completed','failed','cancelled','unknown') or status not in ('running','queued'): break
 time.sleep(2)
