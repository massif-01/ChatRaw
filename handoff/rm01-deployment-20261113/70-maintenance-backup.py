import pathlib,sqlite3,hashlib,json,datetime,importlib.util,shutil,os,subprocess
P=pathlib.Path;os.umask(0o077)
assert all(subprocess.run(['systemctl','is-active','--quiet',s]).returncode!=0 for s in ['chatraw-runner'])
assert subprocess.check_output(['docker','inspect','chatraw','--format','{{.State.Running}}'],text=True).strip()=='false'
base=P('/var/backups/chatraw/20261113T151205Z-isolated-265c378f');root=base/('maintenance-primary-'+datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S'));root.mkdir(mode=0o700);(root/'restored').mkdir(mode=0o700)
helper=P('/home/rm01/chatraw/deployment-e91d32f/ChatRaw-e91d32f/script/agent_db_backup.py');spec=importlib.util.spec_from_file_location('backup_helper',helper);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def logical(p):
 with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:return hashlib.sha256('\n'.join(c.iterdump()).encode()).hexdigest()
volume=P(subprocess.check_output(['docker','volume','inspect','chatraw_chatraw_data','--format','{{.Mountpoint}}'],text=True).strip());sources={'chatraw':volume/'chatraw.db','runner':P('/var/lib/chatraw-runner/runner.db')};before={k:logical(p) for k,p in sources.items()};checks=[]
for name,source in sources.items():
 start=datetime.datetime.now(datetime.timezone.utc).isoformat();dest=root/(name+'.db');mod.backup(source,dest);copy=root/'restored'/dest.name;shutil.copyfile(dest,copy);copy.chmod(0o600)
 with sqlite3.connect('file:'+str(copy)+'?mode=ro',uri=True) as c:integrity=c.execute('pragma integrity_check').fetchone()[0]
 assert integrity=='ok' and logical(copy)==before[name]
 checks.append({'database':name,'started_at':start,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'integrity_check':integrity,'logical_sha256':logical(copy)})
after={k:logical(p) for k,p in sources.items()};assert before==after
c=sqlite3.connect('file:'+str(root/'restored/runner.db')+'?mode=ro',uri=True);assert c.execute("select status from runs where id='e05b8525931c4d1585cae79770c7be3d'").fetchone()[0]=='unknown'
result={'private_directory':str(root),'both_applications_stopped':True,'before_backup_after_logical_states_equal':True,'checks':checks,'old_unknown_preserved':True,'restored_copies_read_only_verified':True,'cross_database_transaction_claimed':False,'native_snapshot_reference':str(base/'backup/runner'),'production_restore_performed':False}
(root/'verification-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
