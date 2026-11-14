"""Prepare or run two serial HTTP-only arms. No SDK, tools, approval, or chat mutation."""
import argparse,pathlib,json,hashlib,copy,os,socket,time,datetime,http.client,io
os.umask(0o077)
p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
a=sub.add_parser('prepare');a.add_argument('--baseline-body',required=True);a.add_argument('--status-body',required=True);a.add_argument('--out',required=True)
a=sub.add_parser('run');a.add_argument('--out',required=True);a.add_argument('--arm',choices=['baseline','status','audit'],required=True);a.add_argument('--released',action='store_true')
args=p.parse_args();root=pathlib.Path(args.out).resolve();assert str(root).startswith(('/tmp/','/private/tmp/')),'Raw diagnostic bodies must remain in private temporary storage'
def digest(b):return hashlib.sha256(b).hexdigest()
def serialize(d):return json.dumps(d,ensure_ascii=False,separators=(',',':')).encode()
def write_json(path,d):path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
if args.command=='prepare':
 assert not root.exists(),'Do not overwrite an existing control'
 source=pathlib.Path(args.baseline_body).read_bytes();status_source=pathlib.Path(args.status_body).read_bytes();baseline=json.loads(source);status=json.loads(status_source)
 assert baseline['model']=='RM-01 VLM' and baseline.get('temperature')==status.get('temperature')==0
 differences=[]
 for i,(a,b) in enumerate(zip(baseline['messages'],status['messages'])):
  if a!=b:differences.append(i)
 assert len(baseline['messages'])==len(status['messages']) and len(differences)==1
 index=differences[0];tool=baseline['messages'][index];changed=status['messages'][index]
 assert tool['role']==changed['role']=='tool' and tool['content']=='(no output)'
 assert changed['content']==tool['content']+'\n[exit code: 0]'
 restored=copy.deepcopy(status);restored['messages'][index]['content']=tool['content'];assert restored==baseline
 success_call_id=tool['tool_call_id'];calls=[c for m in baseline['messages'] for c in (m.get('tool_calls') or []) if c.get('id')==success_call_id];assert len(calls)==1 and calls[0]['function']['name']=='bash'
 call_args=json.loads(calls[0]['function']['arguments']);assert call_args.get('sandbox_permissions')=='danger-full-access'
 assert 'A_NATIVE_e253fd617ca8' in call_args.get('command','')
 # Shared nonstream transport controls; stream_options is invalid with stream=false.
 for body in (baseline,status):
  body.update(stream=False,return_token_ids=True);body.pop('stream_options',None)
 root.mkdir(mode=0o700,parents=True)
 (root/'source-baseline.body').write_bytes(source);(root/'source-status.body').write_bytes(status_source)
 paths={}
 for name,body in [('baseline',baseline),('status',status)]:
  folder=root/name;folder.mkdir(mode=0o700);data=serialize(body);folder.joinpath('request.body').write_bytes(data);paths[name]={'request_sha256':digest(data),'request_bytes':len(data)}
 manifest={'source_baseline_sha256':digest(source),'source_status_sha256':digest(status_source),'source_stage':'native seq54 before final summary; D reconstructed actual SDK body','success_call_id':success_call_id,'success_message_index':index,'approved_command':call_args['command'],'shared_controls':{'stream':False,'return_token_ids':True,'stream_options':'removed because stream=false'},'temperature_from_D':0,'other_request_fields_preserved':True,'only_arm_difference':'messages['+str(index)+'].content','baseline_content':tool['content'],'status_content':status['messages'][index]['content'],'message_count':len(baseline['messages']),'tool_count':len(baseline['tools']),'arms':paths,'upstream':'http://10.10.99.98:58000/v1/chat/completions','tools_executed':0,'new_user_message_added':False,'model_requests_sent':0}
 write_json(root/'manifest.json',manifest);print(json.dumps({'prepared':True,'private_directory':str(root),'success_call_id':success_call_id,'success_message_index':index,'only_arm_difference':manifest['only_arm_difference'],'model_requests_sent':0}))
else:
 assert args.released,'Wait for explicit coordinator release after body/render review'
 manifest=json.loads((root/'manifest.json').read_text());folder=root/args.arm
 if args.arm=='status':assert (root/'baseline/response.metadata.json').exists(),'Finish baseline first'
 if args.arm=='audit':assert (root/'status/response.metadata.json').exists(),'Finish status arm first'
 # Create-once markers prevent accidental double requests and simultaneous arms.
 lock=root/'inflight.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
 try:
  with (folder/'request.sent.json').open('x') as f:json.dump({'arm':args.arm,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},f)
  body=(folder/'request.body').read_bytes();assert digest(body)==manifest['arms'][args.arm]['request_sha256']
  headers={'Host':'10.10.99.98:58000','Content-Type':'application/json','Content-Length':str(len(body)),'Connection':'close'}
  wire=('POST /v1/chat/completions HTTP/1.1\r\n'+''.join(k+': '+v+'\r\n' for k,v in headers.items())+'\r\n').encode()+body;(folder/'request.http.raw').write_bytes(wire)
  start=time.monotonic();first=None;error=None
  try:
   with socket.create_connection(('10.10.99.98',58000),timeout=10) as s,(folder/'response.http.raw').open('wb') as out:
    s.settimeout(900);s.sendall(wire)
    while True:
     block=s.recv(65536)
     if not block:break
     if first is None:first=time.monotonic()-start
     out.write(block);out.flush()
  except OSError as e:error=type(e).__name__+': '+str(e)
  metadata={'arm':args.arm,'request_sha256':digest(body),'first_response_seconds':first,'elapsed_seconds':time.monotonic()-start,'error':error,'tool_execution':False,'requests_sent_max':1}
  rawpath=folder/'response.http.raw'
  if rawpath.exists():
   raw=rawpath.read_bytes();metadata.update(response_http_bytes=len(raw),response_http_sha256=digest(raw))
   class SavedSocket:
    def makefile(self,*a,**kw):return io.BytesIO(raw)
   try:
    response=http.client.HTTPResponse(SavedSocket());response.begin();entity=response.read();(folder/'response.body.raw').write_bytes(entity);metadata.update(status=response.status,response_body_sha256=digest(entity),response_body_bytes=len(entity))
    parsed=json.loads(entity);choices=parsed.get('choices') or [];metadata['choices']=[{'finish_reason':c.get('finish_reason'),'tool_call_count':len(c.get('message',{}).get('tool_calls') or []),'text_chars':len(c.get('message',{}).get('content') or ''),'generated_token_count':len(c.get('token_ids') or [])} for c in choices];metadata['usage']=parsed.get('usage')
   except (ValueError,http.client.HTTPException) as e:metadata['decode_error']=type(e).__name__+': '+str(e)
  write_json(folder/'response.metadata.json',metadata);print(json.dumps(metadata))
 finally:lock.unlink()
