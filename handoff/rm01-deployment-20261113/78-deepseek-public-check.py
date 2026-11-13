"""Bounded API-only approval decisions; SSH is used only after decisions for file evidence."""
from api import api,BASE,opener
import pathlib,json,time,uuid,shlex,subprocess,urllib.request,sys
root=pathlib.Path(__file__).parent
agent,action=sys.argv[1:3]
if agent=='codex':
 prior=json.loads((root/'73-codex-compat-compact/result.json').read_text());chat=prior['chat_id'];binding=api('GET',f'/api/chats/{chat}/agent')
else:
 context=root/'78-deepseek-context.json'
 if context.exists():prior=json.loads(context.read_text());chat=prior['chat_id'];binding=api('GET',f'/api/chats/{chat}/agent')
 else:
  chat=api('POST','/api/chats')['id'];binding=api('PUT',f'/api/chats/{chat}/agent',{'agent_id':'deepseek','workspace':{'kind':'managed'}});context.write_text(json.dumps({'chat_id':chat,'binding':binding},indent=2))
workspace='/var/lib/chatraw-runner/workspaces/'+binding['session_id'];token='A_'+agent.upper()+'_'+uuid.uuid4().hex[:12];target=workspace+'/'+action+'-'+uuid.uuid4().hex+'.txt'
filename=pathlib.Path(target).name
command='printf %s '+token+' > '+filename+' && cat '+filename
message='A field acceptance. Use the native bash tool, not text or any other tool. Include these complete arguments: '+json.dumps({'description':'Write and read the acceptance marker in this session workspace','command':command,'workdir':workspace})+'. Keep command and workdir exactly unchanged. If the native sandbox refuses, request one-time permission for this same command; if permission is denied, stop and report the denial without retrying. Return only the actual command output when allowed.'
run=api('POST','/api/agents/runs',{'chat_id':chat,'client_request_id':uuid.uuid4().hex,'message':message,'attachments':[]});rid=run['run_id'];p=root/f'78-{agent}-{action}.json';out={'agent':agent,'action':action,'chat_id':chat,'binding':binding,'run_id':rid,'command':command,'target':target,'token':token,'approvals':[]};p.write_text(json.dumps(out,indent=2));start=time.monotonic()
for _ in range(120):
 snap=api('GET',f'/api/agents/runs/{rid}');out['snapshot']=snap;p.write_text(json.dumps(out,indent=2))
 if snap['status'] in ('completed','failed','cancelled','unknown','interrupted'):break
 if snap['interactions']:
  if out['approvals'] or len(snap['interactions'])!=1:raise RuntimeError('Unexpected repeated/multiple approval; no approval sent')
  i=snap['interactions'][0];op=i.get('operation',{});actual=op.get('command');exact=actual==command
  if agent=='codex' and isinstance(actual,str):
   try:exact=exact or shlex.split(actual) in (['/bin/bash','-lc',command],['/bin/bash','-c',command])
   except ValueError:pass
  if not exact or op.get('cwd_label')!=workspace:raise RuntimeError('Public approval does not show the exact command and cwd; no approval sent')
  decision=('accept' if agent=='codex' else 'allowed-once') if action=='allow' else 'rejected'
  assert decision in [d['id'] for d in i['decisions']]
  receipt=api('POST',f'/api/agents/runs/{rid}/interactions/{i["interaction_id"]}/reply',{'decision_id':decision});out['approvals'].append({'public_interaction':i,'decision':decision,'receipt':receipt});p.write_text(json.dumps(out,indent=2))
 time.sleep(1)
else:
 out['timeout_cancel_receipt']=api('POST',f'/api/agents/runs/{rid}/cancel',{});p.write_text(json.dumps(out,indent=2));raise RuntimeError('Bounded test timeout; owned run cancellation requested')
out['elapsed']=time.monotonic()-start
req=urllib.request.Request(BASE+f'/api/agents/runs/{rid}/events',headers={'Origin':BASE})
with opener.open(req,timeout=15) as stream,(root/f'78-{agent}-{action}-events.ndjson').open('w') as f:
 for _ in range(snap['last_seq']):
  line=stream.readline()
  if not line:break
  f.write(line.decode())
# This read happens after the public decision, never to fill in missing approval details.
program='import pathlib,json; p=pathlib.Path('+repr(target)+'); print(json.dumps({"exists":p.exists(),"content":p.read_text() if p.is_file() else None}))'
file_state=json.loads(subprocess.check_output(['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99','python3 -c '+shlex.quote(program)],text=True));out['file_state_after']=file_state
out['verdict']='PASS' if out['approvals'] and ((action=='deny' and not file_state['exists'] and snap['status'] in ('completed','failed')) or (action=='allow' and snap['status']=='completed' and file_state['content']==token and token in snap.get('final_text',''))) else 'FAIL'
p.write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
assert out['verdict']=='PASS'
