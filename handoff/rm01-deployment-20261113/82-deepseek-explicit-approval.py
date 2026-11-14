from api import api,BASE,opener
import pathlib,json,time,uuid,subprocess,shlex,urllib.request,sys
root=pathlib.Path(__file__).parent;action=sys.argv[1];assert action in ('deny','allow');ctx=root/'82-deepseek-context.json'
if ctx.exists():context=json.loads(ctx.read_text());chat=context['chat_id'];binding=api('GET',f'/api/chats/{chat}/agent')
else:
 chat=api('POST','/api/chats')['id'];binding=api('PUT',f'/api/chats/{chat}/agent',{'agent_id':'deepseek','workspace':{'kind':'managed'}});ctx.write_text(json.dumps({'chat_id':chat,'binding':binding},indent=2))
workspace='/var/lib/chatraw-runner/workspaces/'+binding['session_id'];filename=action+'-'+uuid.uuid4().hex+'.txt';target=workspace+'/'+filename;token='A_SAFE_'+uuid.uuid4().hex[:12];command='printf %s '+token+' > '+filename
reason='This fixed harmless one-file acceptance command needs one-time permission because the host sandbox backend is unavailable.'
arguments={'description':'Write this one acceptance marker','command':command,'sandbox_permissions':'danger-full-access','justification':reason}
message='A explicit native approval acceptance. Your FIRST and ONLY bash call must use exactly this complete JSON, including sandbox_permissions and justification. Do not first try the default sandbox. Do not retry or use any other tool. If denied, stop immediately and report the denial. If allowed, report the actual tool result.\n'+json.dumps(arguments)
run=api('POST','/api/agents/runs',{'chat_id':chat,'client_request_id':uuid.uuid4().hex,'message':message,'attachments':[]});rid=run['run_id'];path=root/f'82-deepseek-{action}.json';out={'action':action,'chat_id':chat,'binding':binding,'run_id':rid,'first_call_required':arguments,'workspace':workspace,'target':target,'token':token,'approvals':[]};path.write_text(json.dumps(out,indent=2))
def events(last):
 req=urllib.request.Request(BASE+f'/api/agents/runs/{rid}/events',headers={'Origin':BASE});rows=[]
 with opener.open(req,timeout=15) as stream:
  for _ in range(last):
   line=stream.readline()
   if not line:break
   rows.append(json.loads(line))
 return rows
try:
 for _ in range(120):
  snap=api('GET',f'/api/agents/runs/{rid}');out['snapshot']=snap;path.write_text(json.dumps(out,indent=2))
  if snap['status'] in ('completed','failed','cancelled','unknown','interrupted'):break
  if snap['interactions']:
   assert not out['approvals'] and len(snap['interactions'])==1,'Unexpected repeated interaction'
   i=snap['interactions'][0];op=i.get('operation',{});assert i['kind']=='approval' and op.get('tool')=='bash';assert op.get('command')==command and op.get('cwd_label')==workspace,'Public command/cwd mismatch';assert reason in i.get('detail','') and 'danger-full-access' in i['detail'],'Public explanation mismatch'
   public_events=events(snap['last_seq']);starts=[e for e in public_events if e['type']=='tool_started'];assert len(starts)==1 and starts[0]['data']['name']=='bash','Not the first valid bash call'
   decision='rejected' if action=='deny' else 'allowed-once';assert decision in [d['id'] for d in i['decisions']]
   receipt=api('POST',f'/api/agents/runs/{rid}/interactions/{i["interaction_id"]}/reply',{'decision_id':decision});assert receipt['status']=='accepted';out['approvals'].append({'public_interaction':i,'decision':decision,'receipt':receipt,'first_bash_call_verified_from_public_events':True});path.write_text(json.dumps(out,indent=2))
  time.sleep(1)
 else:raise RuntimeError('Bounded test timed out')
except Exception as error:
 out['verification_error']=str(error);current=api('GET',f'/api/agents/runs/{rid}')
 if current['status'] not in ('completed','failed','cancelled','unknown','interrupted'):out['cancel_receipt']=api('POST',f'/api/agents/runs/{rid}/cancel',{})
 path.write_text(json.dumps(out,indent=2));raise
rows=events(snap['last_seq']);(root/f'82-deepseek-{action}-events.ndjson').write_text(''.join(json.dumps(e)+'\n' for e in rows))
program='import pathlib,json; p=pathlib.Path('+repr(target)+');print(json.dumps({"exists":p.exists(),"content":p.read_text() if p.is_file() else None}))'
file_state=json.loads(subprocess.check_output(['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99','python3 -c '+shlex.quote(program)],text=True));out['file_state_after']=file_state
out['verdict']='PASS' if len(out['approvals'])==1 and ((action=='deny' and not file_state['exists'] and snap['status'] in ('completed','failed')) or (action=='allow' and snap['status']=='completed' and file_state['content']==token)) else 'FAIL';path.write_text(json.dumps(out,indent=2));print(json.dumps(out));assert out['verdict']=='PASS'
