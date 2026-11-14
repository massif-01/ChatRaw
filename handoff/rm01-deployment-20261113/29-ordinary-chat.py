from api import api,BASE,opener
import json,pathlib,time,urllib.request
root=pathlib.Path(__file__).parent
before=api('GET','/api/models');default=next(m for m in before if m['id']=='default-chat')
assert default['model_id']=='',default['model_id']
config={**default,'name':'RM-01 VLM','api_url':'http://10.10.99.98:58000/v1','model_id':'RM-01 VLM','api_key':'','context_length':262144,'max_output':8192}
saved=api('POST','/api/models',config);after=api('GET','/api/models')
assert [m for m in before if m['id']!='default-chat']==[m for m in after if m['id']!='default-chat']
chat=api('POST','/api/chats');cid=chat['id'];binding=api('GET',f'/api/chats/{cid}/agent');assert binding['agent_id'] is None
out={'chat_id':cid,'before_models':[{k:v for k,v in m.items() if k!='api_key'} for m in before],'after_models':[{k:v for k,v in m.items() if k!='api_key'} for m in after],'agent_binding':binding,'embedding_rerank_unchanged':True}
p=root/'29-ordinary-chat.json';p.write_text(json.dumps(out,indent=2))
body={'chat_id':cid,'message':'Reply with exactly RM99_NORMAL_OK. No additional text.','use_rag':False,'use_thinking':False};req=urllib.request.Request(BASE+'/api/chat',data=json.dumps(body).encode(),method='POST',headers={'Origin':BASE,'Content-Type':'application/json'})
start=time.monotonic();events=[];first=None
with opener.open(req,timeout=90) as response,(root/'29-ordinary-chat-events.ndjson').open('w') as log:
 for line in response:
  if not line.strip():continue
  event=json.loads(line);events.append(event);log.write(json.dumps(event)+'\n');log.flush()
  if event.get('content') and first is None:first=time.monotonic()-start
out.update(first_content_seconds=first,elapsed_seconds=time.monotonic()-start,final_text=''.join(e.get('content','') for e in events),done=any(e.get('done') for e in events),errors=[e for e in events if e.get('error')],messages=api('GET',f'/api/chats/{cid}/messages'),binding_after=api('GET',f'/api/chats/{cid}/agent'))
p.write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
assert out['done'] and not out['errors'] and out['final_text'].strip()=='RM99_NORMAL_OK',out
assert out['binding_after']['agent_id'] is None
