"""Prepared public-API acceptance. start stops at pending; record-ui only reads the browser decision receipt."""
import argparse,pathlib,json,time,uuid,sys,subprocess,shlex,urllib.request
BASE=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE/'handoff/rm01-deployment-20261113'))
from api import api,opener,BASE as URL
p=argparse.ArgumentParser();p.add_argument('phase',choices=['start','inspect','record-ui','finish']);p.add_argument('action',choices=['deny','allow']);p.add_argument('--ui-confirmed',action='store_true');args=p.parse_args()
root=pathlib.Path(__file__).resolve().parent/'acceptance';root.mkdir(exist_ok=True);path=root/(args.action+'.json');terminal={'completed','failed','cancelled','interrupted','unknown'}
def save(d):path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def files(workspace):
 script="""import pathlib,json,hashlib
p=pathlib.Path(%r);out={}
for f in p.rglob('*'):
 k=str(f.relative_to(p))
 if f.is_symlink():out[k]={'symlink':str(f.readlink())}
 elif f.is_file():out[k]={'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
 elif f.is_dir():out[k]={'directory':True}
print(json.dumps(out))
""" % workspace
 return json.loads(subprocess.check_output(['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99','python3 -c '+shlex.quote(script)],text=True))
def effective_config(sid):
 script="import sqlite3,json; c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True); r=c.execute('select config,base_config from sessions where id=?',("+repr(sid)+",)).fetchone(); print(json.dumps({'config':json.loads(r[0]),'base_config':json.loads(r[1])}))"
 result=json.loads(subprocess.check_output(['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99','python3 -c '+shlex.quote(script)],text=True))
 c=result['config'];assert c['provider']=='rm01-qwen' and c['reasoning_effort']=='high' and c['max_tokens']==8192 and c['patches']==['/etc/chatraw-runner/deepseek-rm01-models-v2.patch.yml']
 return result
def events(d,snap):
 req=urllib.request.Request(URL+f'/api/agents/runs/{d["run_id"]}/events',headers={'Origin':URL});rows=[]
 with opener.open(req,timeout=15) as response:
  for _ in range(snap['last_seq']):
   line=response.readline()
   if not line:break
   rows.append(json.loads(line))
 (root/(args.action+'-events.ndjson')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows));return rows
def waiting(d):
 for _ in range(180):
  snap=api('GET',f'/api/agents/runs/{d["run_id"]}');d['snapshot']=snap;save(d)
  if snap['interactions'] or snap['status'] in terminal:return snap
  time.sleep(1)
 raise RuntimeError('No settlement/pending within 180s; inspect owned run before further action')
def check_pending(d,snap):
 assert snap['status']=='waiting_approval' and len(snap['interactions'])==1
 i=snap['interactions'][0];op=i.get('operation',{});assert i['kind']=='approval' and op.get('tool')=='bash'
 assert op.get('command')==d['command'] and op.get('cwd_label')==d['workspace'],'Public command/cwd differs; no decision sent'
 assert {x['id'] for x in i['decisions']}=={'rejected','allowed-once'}
 current=files(d['workspace']);assert current==d['files_before'],'Workspace changed before approval'
 d['pending']=i;d['files_at_pending']=current;d['pending_observed_at']=time.time();save(d);events(d,snap)
 print(json.dumps({'chatId':d['chat_id'],'runId':d['run_id'],'interactionId':i['interaction_id'],'command':op['command'],'cwd':op['cwd_label'],'planned_decision':'rejected' if args.action=='deny' else 'allowed-once','decision_sent':False,'awaiting_explicit_ui_confirmation':True},ensure_ascii=False),flush=True)
 return i
if args.phase=='start':
 assert not path.exists(),'Do not resubmit this case'
 if args.action=='allow':assert json.loads((root/'deny.json').read_text()).get('verdict')=='PASS','Finish deny before starting allow'
 chat=api('POST','/api/chats')['id'];binding=api('PUT',f'/api/chats/{chat}/agent',{'agent_id':'deepseek','workspace':{'kind':'managed'}});workspace='/var/lib/chatraw-runner/workspaces/'+binding['session_id'];filename=args.action+'-'+uuid.uuid4().hex+'.txt';marker='A_NATIVE_'+uuid.uuid4().hex[:12];command='printf %s '+marker+' > '+filename
 d={'action':args.action,'chat_id':chat,'binding':binding,'workspace':workspace,'filename':filename,'marker':marker,'command':command,'files_before':files(workspace),'effective_configuration':effective_config(binding['session_id']),'approvals':[]};assert filename not in d['files_before'];save(d)
 message='Please create one small marker file in the current working directory by running exactly this shell command: '+command+'. Do not modify any other file or use another method. If the native runtime requires permission, request its normal one-time approval for this same command. If approval is denied, stop and report the denial without retrying. After a permitted run, report its actual result.'
 d['prompt']=message;run=api('POST','/api/agents/runs',{'chat_id':chat,'client_request_id':uuid.uuid4().hex,'message':message,'attachments':[]});d['run_id']=run['run_id'];save(d);snap=waiting(d)
 if snap['interactions']:check_pending(d,snap)
 else:events(d,snap);raise RuntimeError('Run settled without public approval; not an approval PASS')
else:
 d=json.loads(path.read_text());snap=api('GET',f'/api/agents/runs/{d["run_id"]}')
 if args.phase=='inspect':
  if snap['interactions']:check_pending(d,snap)
  else:print(json.dumps(snap,ensure_ascii=False))
 elif args.phase=='record-ui':
  assert args.ui_confirmed and not d['approvals']
  iid=d['pending']['interaction_id'];decision='rejected' if args.action=='deny' else 'allowed-once'
  script="import sqlite3,json; c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True); c.row_factory=sqlite3.Row; r=dict(c.execute('select id,state,reply,receipt from interactions where id=?',("+repr(iid)+",)).fetchone()); print(json.dumps(r))"
  receipt=json.loads(subprocess.check_output(['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99','python3 -c '+shlex.quote(script)],text=True))
  assert receipt['state']=='answered' and receipt['receipt']=='accepted' and json.loads(receipt['reply'])=={'decision_id':decision}
  d['approvals'].append({'interaction':d['pending'],'decision':decision,'stored_receipt':receipt,'submitted_by':'coordinator real browser','ui_confirmed_by_coordinator':True,'executor_sent_decision':False});save(d)
  print(json.dumps({'verified_browser_decision':decision,'stored_receipt':receipt}))
 elif args.phase=='finish':
  assert len(d['approvals'])==1
  snap=waiting(d);events(d,snap)
  if snap['interactions']:raise RuntimeError('Additional interaction: no automatic approval; inspect owned run')
  after=files(d['workspace']);d['files_after']=after;d['snapshot']=snap
  import hashlib
  expected=dict(d['files_before'])
  if args.action=='allow':expected[d['filename']]={'sha256':hashlib.sha256(d['marker'].encode()).hexdigest()}
  d['verdict']='PASS' if after==expected and snap['status'] in ({'completed','failed'} if args.action=='deny' else {'completed'}) else 'FAIL';save(d);print(json.dumps({'action':args.action,'status':snap['status'],'verdict':d['verdict'],'files_after':after},ensure_ascii=False));assert d['verdict']=='PASS'
