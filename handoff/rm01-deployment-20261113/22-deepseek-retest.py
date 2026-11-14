from api import api
import json,time,uuid,pathlib
root=pathlib.Path(__file__).parent
old=json.loads((root/'07-deepseek.json').read_text());chat=old['chat_id']
settings=api('POST','/api/plugins/deepseek/settings',{'settings':{'model':'RM-01 VLM','max_tokens':8192}})
before=api('GET',f'/api/chats/{chat}/agent');start=time.time()
run=api('POST','/api/agents/runs',{'chat_id':chat,'client_request_id':str(uuid.uuid4()),'message':'This is a new validation turn. Actually use your native bash tool to run pwd now, exactly once. Then report the actual working directory and RM99_DEEPSEEK_OK. Do not rely on prior summaries as evidence of running this command. Do not access files or make network requests.','attachments':[]})
out={'agent':'deepseek','chat_id':chat,'settings_response':settings,'before':before,'submitted':run};path=root/'22-deepseek-retest.json';path.write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
for _ in range(180):
 snap=api('GET',f"/api/agents/runs/{run['run_id']}")
 out.update(snapshot=snap,elapsed=round(time.time()-start,2));path.write_text(json.dumps(out,indent=2))
 if snap['status'] not in ('running','queued'):break
 time.sleep(2)
print(json.dumps(out),flush=True)
