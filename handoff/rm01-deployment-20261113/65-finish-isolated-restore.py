"""Finish the already captured private backup; do not capture again or start services."""
import pathlib,json,sqlite3,hashlib,shutil,datetime,os
P=pathlib.Path;os.umask(0o077)
stage=P('/var/backups/chatraw/20261113T151205Z-isolated-265c378f');m=json.loads((stage/'private-manifest.json').read_text());backup=stage/'backup';restore=stage/'restore'
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def db(path):
 c=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
runner_live=db('/var/lib/chatraw-runner/runner.db')
active=[dict(r) for r in runner_live.execute("select id,status from runs where status not in ('completed','failed','cancelled','interrupted')")]
assert active==[{'id':'e05b8525931c4d1585cae79770c7be3d','status':'unknown'}]
assert m['changed_regular_files']==[]
changed={label:[t for t,x in before['tables'].items() if m['core_after'][label]['tables'].get(t)!=x] for label,before in m['core_before'].items()}
assert changed=={'chatraw':['chats'],'runner':[]},changed
# Establish the exact metadata-only boundary, without copying live data again.
a=db(backup/'chatraw/chatraw.db');live=db(P(m['roots']['chatraw'])/'chatraw.db')
aa={r['id']:dict(r) for r in a.execute('select * from chats')};bb={r['id']:dict(r) for r in live.execute('select * from chats')};assert aa.keys()==bb.keys()
metadata_changes=[]
for key in aa:
 cols=[col for col in aa[key] if aa[key][col]!=bb[key][col]]
 assert not cols or cols==['updated_at'],cols
 if cols:metadata_changes.append({'chat_id':key,'columns':cols})
# The first verification already created this private copy; never recopy live data.
assert restore.is_dir()
for item in m['files']:assert sha(restore/item['relative'])==item['sha256']
databases=[]
for item in m['databases']:
 path=restore/item['relative'];c=db(path);integrity=c.execute('pragma integrity_check').fetchone()[0];assert integrity=='ok';assert sha(path)==item['backup_sha256'];databases.append({'database':item['relative'],'integrity_check':integrity,'backup_bytes_match':True});c.close()
chat=db(restore/'chatraw/chatraw.db');runner=db(restore/'runner/runner.db');sessions={r['id']:dict(r) for r in runner.execute('select id,chat_id,agent_id,workspace,binding from sessions')};bindings=[dict(r) for r in chat.execute('select chat_id,agent_id,session_id from agent_bindings where session_id is not null')]
for b in bindings:assert sessions[b['session_id']]['chat_id']==b['chat_id'] and sessions[b['session_id']]['agent_id']==b['agent_id']
workspaces=0
for s in sessions.values():
 rel=P(s['workspace']).relative_to('/var/lib/chatraw-runner');assert (restore/'runner'/rel).is_dir();workspaces+=1
workspace_files=[x for x in m['files'] if x['relative'].startswith('runner/workspaces/')]
sample=next(x for x in workspace_files if x['relative'].endswith('/d-a088ad3f5ddf45edbb7830e09dabb7ba.started'))
assert sha(restore/sample['relative'])==sample['sha256']
# Representative native state references; no native format parsing or execution.
examples={
 'codex':list((restore/'runner/codex-home/sessions').rglob('*01a1d516-d830-7742-b766-ff1071485eaf*.jsonl')),
 'claude':list((restore/'runner/claude-home').rglob('ffe300d5-6381-40f5-8672-19a50375e8d4.jsonl')),
 'pi':[restore/'runner/pi-sessions/3e9d8bc52dc74ac68878f467ec150036/session.jsonl'],
 'deepseek':list((restore/'runner/deepseek/session-2c63be8b22744b3cb0c81413a51f6aad').rglob('session.v4.jsonl.zstd')),
 'hermes':[restore/'runner/hermes-home/state.db']}
for paths in examples.values():assert paths and all(p.is_file() for p in paths)
cid='6a5b5091-00be-4bf3-90cf-303160876c4a';message_counts={'messages':chat.execute('select count(*) from messages where chat_id=?',(cid,)).fetchone()[0],'agent_projection_links':chat.execute('select count(*) from agent_messages a join messages m on m.id=a.message_id where m.chat_id=?',(cid,)).fetchone()[0]};assert message_counts=={'messages':12,'agent_projection_links':12}
old=dict(runner.execute("select id,status from runs where id='e05b8525931c4d1585cae79770c7be3d'").fetchone());assert old['status']=='unknown'
assert [dict(r) for r in runner_live.execute("select id,status from runs where status not in ('completed','failed','cancelled','interrupted')")]==active
primary_windows=[{'database':x['relative'],'started_at':x['started_at'],'finished_at':x['finished_at']} for x in m['databases'] if x['relative'] in ('chatraw/chatraw.db','runner/runner.db')]
result={'verdict':'SELECTED_READ_ONLY_RESTORE_VERIFIED','private_directory':str(stage),'directory_mode':oct(stage.stat().st_mode&0o777),'backup_started_at':m['started_at'],'backup_manifest_written_at':datetime.datetime.fromtimestamp((stage/'private-manifest.json').stat().st_mtime,datetime.timezone.utc).isoformat(),'verification_finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'primary_snapshot_windows':primary_windows,'primary_whole_state_unchanged':False,'observed_metadata_changes':metadata_changes,'message_binding_configuration_and_runner_tables_unchanged':True,'regular_files_unchanged_during_backup':True,'database_checks':databases,'regular_files_restored_and_hashed':len(m['files']),'regular_bytes':sum(f['size'] for f in m['files']),'restored_bindings_checked':len(bindings),'restored_managed_directories_checked':workspaces,'restored_workspace_file_count':len(workspace_files),'representative_marker_sha256':sample['sha256'],'representative_native_state_present':{a:len(paths) for a,paths in examples.items()},'user_original_message_counts':message_counts,'old_unknown':old,'nonterminal_after':active,'runtime_symlinks_and_sockets_not_restored':len(m['skipped']),'production_data_switched':False,'restored_services_or_native_agents_started':False,'cross_database_transaction_consistency_claimed':False,'full_startup_or_power_loss_recovery_verified':False,'private_manifest_sha256':sha(stage/'private-manifest.json')}
(stage/'verification-result.json').write_text(json.dumps(result,indent=2));(stage/'verification-result.json').chmod(0o600)
print(json.dumps(result,indent=2))
