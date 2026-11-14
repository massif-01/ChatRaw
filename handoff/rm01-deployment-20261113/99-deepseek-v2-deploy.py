"""Run on .99 as root only after F and coordinator release this exact candidate."""
import pathlib,json,hashlib,sqlite3,subprocess,shutil,os,sys
if sys.argv[1:]!=['--apply-reviewed']:raise SystemExit('Prepared only. Requires --apply-reviewed after coordinator release.')
assert os.geteuid()==0
root=pathlib.Path(__file__).resolve().parent;manifest=json.loads((root/'manifest.json').read_text());dest=pathlib.Path('/opt/chatraw-runner/agent_runner/adapters/deepseek.py');cfg=pathlib.Path('/etc/chatraw-runner/config.json');v1=cfg.with_name('deepseek-rm01-models-v1.patch.yml');v2=cfg.with_name('deepseek-rm01-models-v2.patch.yml')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def db_snapshot():
 c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True)
 return {'sessions':c.execute('select id,binding,base_config from sessions order by id').fetchall(),'nonterminal':c.execute("select id,status from runs where status not in ('completed','failed','cancelled','interrupted') order by id").fetchall()}
for name,digest in manifest['files'].items():assert sha(root/name)==digest
assert sha(dest)==manifest['expected_current_adapter_sha256'],'Runtime changed; review before deployment'
assert not v2.exists(),'Versioned patch already exists; do not overwrite'
before=db_snapshot();assert all(tuple(r)==('e05b8525931c4d1585cae79770c7be3d','unknown') for r in before['nonterminal']),'Other active work; do not stop Runner'
config=json.loads(cfg.read_text());assert 'provider' not in config['agents']['deepseek'];assert config['agents']['deepseek']['patches']==[str(v1)]
# Public settings already hold model/high/8192; check without modifying plugin stores.
c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True);settings=json.loads(c.execute("select settings from agents where id='deepseek'").fetchone()[0]);assert settings.get('model')=='RM-01 VLM' and settings.get('max_tokens')==8192 and ('reasoning_effort' not in settings or settings['reasoning_effort']=='high'), 'Public settings changed; do not override user selection'
v1hash=sha(v1);backup=root/'before';backup.mkdir(mode=0o700)
for p,name in [(dest,'deepseek.py'),(cfg,'config.json'),(v1,'v1.patch.yml')]:shutil.copy2(p,backup/name);(backup/name).chmod(0o600)
(backup/'sessions.json').write_text(json.dumps(before));(backup/'sessions.json').chmod(0o600)
subprocess.run(['systemctl','stop','chatraw-runner'],check=True)
try:
 assert db_snapshot()['sessions']==before['sessions']
 shutil.copyfile(root/'deepseek.py',dest);os.chown(dest,0,0);dest.chmod(0o644)
 shutil.copyfile(root/'deepseek-rm01-models-v2.patch.yml',v2);os.chown(v2,0,v1.stat().st_gid);v2.chmod(0o440)
 config['agents']['deepseek'].update(provider='rm01-qwen',patches=[str(v2)],reasoning_effort='high',max_tokens=8192)
 effective={**config['agents']['deepseek'],**settings};assert effective['reasoning_effort']=='high' and effective['max_tokens']==8192
 cfg.write_text(json.dumps(config,indent=2)+'\n')
 assert sha(v1)==v1hash and db_snapshot()['sessions']==before['sessions']
finally:subprocess.run(['systemctl','start','chatraw-runner'],check=True)
subprocess.run(['systemctl','is-active','chatraw-runner'],check=True)
assert db_snapshot()['sessions']==before['sessions']
print(json.dumps({'candidate_commit':manifest['candidate_commit'],'adapter_sha256':sha(dest),'v2_sha256':sha(v2),'v1_unchanged':sha(v1)==v1hash,'all_old_bindings_and_host_snapshots_preserved':True,'provider_for_new_bindings':'rm01-qwen','runner_restart_only':True,'effective_reasoning_effort':effective['reasoning_effort'],'effective_max_tokens':effective['max_tokens'],'public_settings_unchanged':True,'backup_directory':str(backup)}))
