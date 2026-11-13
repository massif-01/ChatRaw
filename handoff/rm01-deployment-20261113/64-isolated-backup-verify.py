"""Run as host administrator: private snapshots and read-only isolated validation."""
import datetime, hashlib, importlib.util, json, os, pathlib, shutil, sqlite3, stat, subprocess, uuid
from urllib.parse import quote
P = pathlib.Path
os.umask(0o077)
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def conn(path): return sqlite3.connect('file:'+quote(str(path))+'?mode=ro',uri=True)
def db_state(path):
    with conn(path) as c:
        c.execute('BEGIN')
        schemas=c.execute("select name,sql from sqlite_master where type='table' and name not like 'sqlite_%' order by name").fetchall()
        tables={}
        for name,sql in schemas:
            rows=c.execute('select * from "'+name.replace('"','""')+'"').fetchall()
            encoded=sorted(json.dumps(r,default=lambda b:{'blob_hex':b.hex()},separators=(',',':')) for r in rows)
            tables[name]={'rows':len(rows),'sha256':hashlib.sha256(('\n'.join(encoded)).encode()).hexdigest()}
        return {'schema_sha256':hashlib.sha256(json.dumps(schemas).encode()).hexdigest(),'tables':tables}
def gate():
    with conn(P('/var/lib/chatraw-runner/runner.db')) as c:
        rows=c.execute("select id,status from runs where status not in ('completed','failed','cancelled','interrupted')").fetchall()
    if any(r!=('e05b8525931c4d1585cae79770c7be3d','unknown') for r in rows): raise RuntimeError('Real active task detected; no task was cancelled')
    return rows
started=now();gate_before=gate()
volume=P(subprocess.check_output(['docker','volume','inspect','chatraw_chatraw_data','--format','{{.Mountpoint}}'],text=True).strip())
roots={'chatraw':volume,'runner':P('/var/lib/chatraw-runner'),'config':P('/etc/chatraw-runner')}
helper=P('/home/rm01/chatraw/deployment-e91d32f/ChatRaw-e91d32f/script/agent_db_backup.py')
spec=importlib.util.spec_from_file_location('existing_sqlite_backup',helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
parent=P('/var/backups/chatraw');parent.mkdir(parents=True,exist_ok=True);parent.chmod(0o700)
stage=parent/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-isolated-'+uuid.uuid4().hex[:8]);stage.mkdir(mode=0o700)
backup=stage/'backup';restored=stage/'restore';backup.mkdir(mode=0o700)
core_before={name:db_state(root/filename) for name,root,filename in [('chatraw',volume,'chatraw.db'),('runner',roots['runner'],'runner.db')]}
files=[];skipped=[];databases=[]
for label,root in roots.items():
    for base,dirs,names in os.walk(root,followlinks=False):
        for name in dirs+names:
            path=P(base)/name;mode=path.lstat().st_mode;relative=path.relative_to(root);dest=backup/label/relative
            if stat.S_ISLNK(mode):skipped.append({'path':str(path),'reason':'runtime symlink; not followed'});continue
            if stat.S_ISDIR(mode):dest.mkdir(parents=True,exist_ok=True,mode=0o700);continue
            if not stat.S_ISREG(mode):skipped.append({'path':str(path),'reason':'live socket or non-regular object'});continue
            with path.open('rb') as f:header=f.read(16)
            record={'source':str(path),'relative':str(P(label)/relative)}
            if header==b'SQLite format 3\0':databases.append(record)
            else:files.append(record)
sidecars={d['source']+suffix for d in databases for suffix in ('-wal','-shm','-journal')}
files=[f for f in files if f['source'] not in sidecars]
private={'started_at':started,'backup_helper_sha256':sha(helper),'roots':{k:str(v) for k,v in roots.items()},'files':[],'databases':[],'skipped':skipped,'sqlite_sidecars_excluded':sorted(sidecars)}
for d in databases:
    source=P(d['source']);dest=backup/d['relative'];dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    before=db_state(source);stamp=now();module.backup(source,dest);after=db_state(source)
    private['databases'].append({**d,'started_at':stamp,'finished_at':now(),'source_before':before,'source_after':after,'backup_state':db_state(dest),'backup_sha256':sha(dest)})
for f in files:
    source=P(f['source']);dest=backup/f['relative'];dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    shutil.copyfile(source,dest);dest.chmod(0o600);private['files'].append({**f,'sha256':sha(dest),'size':dest.stat().st_size})
# Keep the exact service and Compose control files with the private archive.
controls=[P('/etc/systemd/system/chatraw-runner.service'),P('/etc/systemd/system/chatraw-hermes.service'),P('/home/rm01/chatraw/deployment-e91d32f/compose.prebuilt.yml'),P('/home/rm01/chatraw/deployment-e91d32f/ChatRaw-e91d32f/docker-compose.yml'),P('/home/rm01/chatraw/deployment-e91d32f/ChatRaw-e91d32f/deploy/docker-compose.agent.yml')]
for source in controls:
    dest=backup/'controls'/source.name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700);shutil.copyfile(source,dest);dest.chmod(0o600);private['files'].append({'source':str(source),'relative':str(dest.relative_to(backup)),'sha256':sha(dest),'size':dest.stat().st_size})
core_after={name:db_state(root/filename) for name,root,filename in [('chatraw',volume,'chatraw.db'),('runner',roots['runner'],'runner.db')]}
gate_after=gate();changed_files=[f['relative'] for f in private['files'] if not P(f['source']).is_file() or sha(P(f['source']))!=f['sha256']]
native_changed=[]
for d in private['databases']:
    final=db_state(P(d['source']));d['source_end']=final
    for table,info in d['source_before']['tables'].items():
        if final['tables'].get(table)!=info or d['backup_state']['tables'].get(table)!=info:native_changed.append({'database':d['relative'],'table':table})
private['core_before']=core_before;private['core_after']=core_after;private['changed_regular_files']=changed_files;private['changed_database_tables']=native_changed
(stage/'private-manifest.json').write_text(json.dumps(private,indent=2));(stage/'private-manifest.json').chmod(0o600)
if core_before!=core_after:raise RuntimeError('Primary application state changed during snapshot window; private backups retained but verification stopped')
for label in ('chatraw','runner'):
    d=next(d for d in private['databases'] if d['relative']==label+'/'+label+'.db')
    if d['backup_state']!=core_before[label]:raise RuntimeError('Primary backup differs from observation boundary; no production restore performed')
if changed_files:raise RuntimeError('Source regular files changed during snapshot window; private backups retained but verification stopped')
# Restore only into a new private directory. Never start an app or native runtime.
shutil.copytree(backup,restored)
for f in private['files']:
    if sha(restored/f['relative'])!=f['sha256']:raise RuntimeError('Restored file hash mismatch')
checks=[]
for d in private['databases']:
    path=restored/d['relative']
    with conn(path) as c:ok=c.execute('pragma integrity_check').fetchone()[0]
    if ok!='ok' or db_state(path)!=d['backup_state']:raise RuntimeError('Restored SQLite verification failed')
    checks.append({'database':d['relative'],'integrity_check':'ok','logical_state_matches_backup':True})
chat=conn(restored/'chatraw/chatraw.db');chat.row_factory=sqlite3.Row
runner=conn(restored/'runner/runner.db');runner.row_factory=sqlite3.Row
sessions={r['id']:dict(r) for r in runner.execute('select id,chat_id,agent_id,workspace,binding from sessions')}
bindings=list(chat.execute('select chat_id,agent_id,session_id from agent_bindings where session_id is not null'))
for b in bindings:
    target=sessions[b['session_id']]
    if target['chat_id']!=b['chat_id'] or target['agent_id']!=b['agent_id']:raise RuntimeError('Restored binding identity mismatch')
def mapped(path):
    path=P(path)
    for label,root in roots.items():
        if path.is_relative_to(root):return restored/label/path.relative_to(root)
    raise RuntimeError('Referenced path lies outside the declared backup set')
workspace_count=0;native_counts={};unmaterialized=0
hermes=conn(restored/'runner/hermes-home/state.db')
for s in sessions.values():
    if not mapped(s['workspace']).is_dir():raise RuntimeError('Restored managed workspace is missing')
    workspace_count+=1;b=json.loads(s['binding']) if s['binding'] else {};n=b.get('native',{});a=s['agent_id']
    if not n:unmaterialized+=1;continue
    if a=='codex':found=list((restored/'runner/codex-home/sessions').rglob('*'+n['thread_id']+'*.jsonl'))
    elif a=='claude':found=list((restored/'runner/claude-home').rglob(n['session_id']+'.jsonl'))
    elif a=='pi':found=[mapped(n['transcript'])] if mapped(n['transcript']).is_file() else []
    elif a=='deepseek':found=list(mapped(n['dsh_home']).rglob('session.v4.jsonl.zstd'))
    elif a=='hermes':found=hermes.execute('select id from sessions where id=?',(n['session_id'],)).fetchall()
    else:raise RuntimeError('Unexpected adapter in restore set')
    if not found:raise RuntimeError('Referenced native state not found in restored copy')
    native_counts[a]=native_counts.get(a,0)+1
old_unknown=dict(runner.execute("select id,status,error from runs where id='e05b8525931c4d1585cae79770c7be3d'").fetchone())
if old_unknown['status']!='unknown':raise RuntimeError('Original unknown not preserved')
user_count=chat.execute("select count(*) from messages where chat_id='6a5b5091-00be-4bf3-90cf-303160876c4a'").fetchone()[0]
public={'verdict':'READ_ONLY_RESTORE_VERIFIED','private_directory':str(stage),'directory_mode':oct(stage.stat().st_mode&0o777),'started_at':started,'finished_at':now(),'primary_before_after_equal':True,'primary_backups_match_observed_state':True,'database_checks':checks,'regular_files_restored_and_hashed':len(private['files']),'regular_bytes':sum(f['size'] for f in private['files']),'changed_regular_files':changed_files,'native_database_tables_changed_during_window':native_changed,'runtime_symlinks_and_sockets_excluded':len(skipped),'restored_bindings_checked':len(bindings),'restored_workspaces_checked':workspace_count,'native_state_references_checked':native_counts,'unmaterialized_sessions':unmaterialized,'user_original_message_count':user_count,'old_unknown':{'run_id':old_unknown['id'],'status':old_unknown['status']},'initial_nonterminal':gate_before,'final_nonterminal':gate_after,'production_data_switched':False,'native_or_application_started_from_restore':False,'transaction_consistency_claimed':False,'private_manifest_sha256':sha(stage/'private-manifest.json')}
(stage/'verification-result.json').write_text(json.dumps(public,indent=2));(stage/'verification-result.json').chmod(0o600)
print(json.dumps(public,indent=2))
