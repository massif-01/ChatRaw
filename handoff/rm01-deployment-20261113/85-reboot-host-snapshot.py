"""Read-only pre/post reboot baseline. Run through the existing SSH control connection."""
import pathlib,json,sqlite3,hashlib,subprocess,re,datetime,os
P=pathlib.Path
def run(argv):
 r=subprocess.run(argv,capture_output=True,text=True);return r.returncode,r.stdout.strip()
def hashfile(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def unit(name,user=False):
 cmd=['systemctl']+(['--user'] if user else [])+['show',name,'-p','Id','-p','LoadState','-p','ActiveState','-p','SubState','-p','UnitFileState','-p','FragmentPath','-p','MainPID','-p','ActiveEnterTimestamp','-p','ActiveEnterTimestampMonotonic','-p','NRestarts','-p','ExecMainStatus']
 if user:cmd=['sudo','-u','rm01','env','XDG_RUNTIME_DIR=/run/user/1000']+cmd
 code,text=run(cmd);d=dict(line.split('=',1) for line in text.splitlines() if '=' in line);d['query_exit']=code
 if d.get('FragmentPath') and P(d['FragmentPath']).is_file():d['unit_sha256']=hashfile(P(d['FragmentPath']))
 return d
c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True);c.row_factory=sqlite3.Row
sessions=[dict(r) for r in c.execute('select id,chat_id,agent_id,workspace,binding,base_config from sessions order by id')]
runs=[dict(r) for r in c.execute('select id,session_id,chat_id,kind,status,created_at,fingerprint,last_seq,error from runs order by id')]
container=json.loads(subprocess.check_output(['docker','inspect','chatraw']))[0]
services={name:unit(name) for name in ('docker.service','containerd.service','chatraw-runner.service','chatraw-hermes.service','lpmustatus-api.service','nfs-server.service','nfs-mountd.service','rpcbind.service','smbd.service','nmbd.service')};services['user:tto-web.service']=unit('tto-web.service',True)
listeners=[]
for line in subprocess.check_output(['ss','-lntp'],text=True).splitlines()[1:]:
 parts=line.split();port=parts[3].rsplit(':',1)[-1]
 if port not in {'51111','51112','59090','59009','2049','445','139'}:continue
 processes=[]
 for pid in re.findall(r'pid=(\d+)',line):
  base=P('/proc')/pid
  try:processes.append({'pid':int(pid),'cgroup':(base/'cgroup').read_text().strip(),'exe':str((base/'exe').resolve()),'cwd':str((base/'cwd').resolve())})
  except FileNotFoundError:pass
 listeners.append({'address':parts[3],'port':int(port),'processes':processes})
configs=['/etc/chatraw-runner/config.json','/etc/chatraw-runner/environment','/etc/chatraw-runner/token','/etc/chatraw-runner/deepseek-rm01-models-v1.patch.yml','/var/lib/chatraw-runner/codex-home/config.toml','/var/lib/chatraw-runner/pi-home/models.json','/var/lib/chatraw-runner/pi-home/settings.json','/var/lib/chatraw-runner/hermes-home/config.yaml','/etc/exports','/etc/samba/smb.conf']
files={x:hashfile(P(x)) for x in configs if P(x).is_file()}
workspace_files={str(p):hashfile(p) for p in P('/var/lib/chatraw-runner/workspaces').rglob('*') if p.is_file() and not p.is_symlink()}
exports_code,exports=run(['exportfs','-s']);smb_code,smb=run(['testparm','-s','--suppress-prompt'])
volume=next(x['Source'] for x in container['Mounts'] if x.get('Name')=='chatraw_chatraw_data');chat=sqlite3.connect('file:'+volume+'/chatraw.db?mode=ro',uri=True)
def table_hash(table):
 rows=chat.execute('select * from '+table).fetchall();serialized=sorted(json.dumps(r,default=lambda x:x.hex(),separators=(',',':')) for r in rows);return {'rows':len(rows),'sha256':hashlib.sha256('\n'.join(serialized).encode()).hexdigest()}
plugin=P(volume)/'plugins/config.json'
result={'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'boot_id':P('/proc/sys/kernel/random/boot_id').read_text().strip(),'uptime_seconds':float(P('/proc/uptime').read_text().split()[0]),'hostname':run(['hostname'])[1],'user_linger':run(['loginctl','show-user','rm01','-p','Linger','-p','State'])[1],'services':services,'listeners':listeners,'container':{'id':container['Id'],'image_id':container['Image'],'configured_image':container['Config']['Image'],'mounts':container['Mounts'],'restart_policy':container['HostConfig']['RestartPolicy'],'network_mode':container['HostConfig']['NetworkMode'],'state':{k:container['State'][k] for k in ('Status','Running','StartedAt','FinishedAt','ExitCode')},'restart_count':container['RestartCount']},'stable_config_hashes':files,'plugin_config_sha256':hashfile(plugin),'chatraw_data_tables':{t:table_hash(t) for t in ('settings','model_configs','messages','agent_bindings','agent_messages','agent_submissions')},'workspace_file_hashes':workspace_files,'sessions':sessions,'runs':runs,'nonterminal':[r for r in runs if r['status'] not in ('completed','failed','cancelled','interrupted')],'nfs_exports':{'exit_code':exports_code,'sorted_content_sha256':hashlib.sha256('\n'.join(sorted(exports.splitlines())).encode()).hexdigest()},'smb_effective_config':{'exit_code':smb_code,'sha256':hashlib.sha256(smb.encode()).hexdigest()}}
print(json.dumps(result,indent=2))
