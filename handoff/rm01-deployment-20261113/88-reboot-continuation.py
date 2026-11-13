from api import api,BASE,opener
import pathlib,json,time,uuid,urllib.request,datetime
root=pathlib.Path(__file__).parent;targets=json.loads((root/'87-reboot-continuation-plan.json').read_text())
for target in targets:
 agent=target['agent'];chat=target['chat_id'];before=api('GET',f'/api/chats/{chat}/agent');assert before['session_id']==target['runner_session'] and before['active_run_id'] is None
 started=time.monotonic();run=api('POST','/api/agents/runs',{'chat_id':chat,'client_request_id':uuid.uuid4().hex,'message':'Without using any tools, return only the D- prefixed continuity code saved earlier in this conversation. Use the existing conversation context.','attachments':[]});rid=run['run_id'];out={'agent':agent,'chat_id':chat,'expected_marker':target['expected_marker'],'runner_session':target['runner_session'],'before_native_identity':target['native_identity'],'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run_id':rid,'binding_before':before};path=root/f'88-{agent}-continuation.json';path.write_text(json.dumps(out,indent=2))
 for _ in range(90):
  snap=api('GET',f'/api/agents/runs/{rid}');out['snapshot']=snap;path.write_text(json.dumps(out,indent=2))
  if snap['status'] in ('completed','failed','cancelled','interrupted','unknown'):break
  if snap['status'] in ('waiting_approval','waiting_input'):
   out['unexpected_interaction']=True;out['cancel_receipt']=api('POST',f'/api/agents/runs/{rid}/cancel',{});path.write_text(json.dumps(out,indent=2));raise RuntimeError('Text-only continuation unexpectedly requested an interaction; no approval given')
  time.sleep(2)
 else:
  out['cancel_receipt']=api('POST',f'/api/agents/runs/{rid}/cancel',{});path.write_text(json.dumps(out,indent=2));raise RuntimeError('Text-only continuation timed out; owned test run cancellation requested')
 req=urllib.request.Request(BASE+f'/api/agents/runs/{rid}/events',headers={'Origin':BASE});events=[]
 with opener.open(req,timeout=15) as stream:
  for _ in range(snap['last_seq']):
   line=stream.readline()
   if not line:break
   events.append(json.loads(line))
 (root/f'88-{agent}-events.ndjson').write_text(''.join(json.dumps(e)+'\n' for e in events));out.update(elapsed_seconds=round(time.monotonic()-started,3),tool_events=sum(e['type']=='tool_started' for e in events),binding_after=api('GET',f'/api/chats/{chat}/agent'))
 out['verdict']='PASS' if snap['status']=='completed' and snap.get('final_text','').strip().strip('`"')==target['expected_marker'] and out['tool_events']==0 and out['binding_after']['session_id']==target['runner_session'] else 'FAIL';path.write_text(json.dumps(out,indent=2));print(json.dumps({'agent':agent,'verdict':out['verdict'],'status':snap['status'],'final_text':snap.get('final_text'),'elapsed_seconds':out['elapsed_seconds']}),flush=True)
 if snap['status']=='unknown':break
