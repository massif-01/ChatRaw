from api import api,opener,BASE
import json,time,sys,uuid,pathlib,urllib.request,threading
root=pathlib.Path(__file__).parent
for agent in sys.argv[1:]:
 old=json.loads((root/f'07-{agent}.json').read_text());chat=old['chat_id'];start=time.time()
 run=api('POST','/api/agents/runs',{'chat_id':chat,'client_request_id':str(uuid.uuid4()),'message':'Without using any tools, output the integers from 1 through 5000, one integer per line. Begin immediately and do not summarize or abbreviate. This is a streaming cancellation test.','attachments':[]})
 rid=run['run_id'];first=threading.Event();events=[];errors=[]
 def consume():
  try:
   req=urllib.request.Request(BASE+f'/api/agents/runs/{rid}/events',headers={'Origin':BASE})
   with opener.open(req,timeout=45) as response,(root/f'16-{agent}-cancel-events.ndjson').open('w') as out:
    for line in response:
     if not line.strip():continue
     event=json.loads(line);events.append(event);out.write(json.dumps(event)+'\n');out.flush()
     if event['type']=='text_delta':first.set()
  except Exception as e: errors.append(str(e))
 thread=threading.Thread(target=consume,daemon=True);thread.start()
 first.wait(45)
 before=api('GET',f'/api/agents/runs/{rid}')
 out={'agent':agent,'submitted':run,'first_content_observed':first.is_set(),'before_cancel':before,'elapsed_before_cancel':round(time.time()-start,2)}
 if before['status'] not in ('completed','failed','cancelled'):
  out['cancel_receipt']=api('POST',f'/api/agents/runs/{rid}/cancel',{})
  for _ in range(35):
   snap=api('GET',f'/api/agents/runs/{rid}')
   if snap['status'] in ('completed','failed','cancelled','unknown'):break
   time.sleep(1)
  out['after_cancel']=snap
 thread.join(5);out['event_reader_errors']=errors;out['elapsed']=round(time.time()-start,2)
 (root/f'16-{agent}-cancel.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
 if out.get('after_cancel',{}).get('status')!='cancelled':break
