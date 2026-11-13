"""Read only this acceptance session's native events and stored public receipts."""
import pathlib,sqlite3,json,subprocess,sys
sid=sys.argv[1];c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True);c.row_factory=sqlite3.Row
session=dict(c.execute('select id,chat_id,binding,base_config,config from sessions where id=?',(sid,)).fetchone());session={k:json.loads(v) if k in ('binding','base_config','config') else v for k,v in session.items()};home=pathlib.Path(session['binding']['native']['dsh_home']);logs=list(home.rglob('session.v4.jsonl.zstd'));assert len(logs)==1
rows=[json.loads(line) for line in subprocess.check_output(['zstd','-dc',str(logs[0])],stderr=subprocess.DEVNULL).decode().splitlines()]
keep=[e for e in rows if e.get('type','').startswith(('approval/','tool/','turn/','job/','permission/','sandbox/'))]
receipts=[dict(r) for r in c.execute('select i.id,i.run_id,i.state,i.reply,i.receipt from interactions i join runs r on r.id=i.run_id where r.session_id=? order by i.id',(sid,))]
print(json.dumps({'session':session,'native_record_count':len(rows),'events':keep,'public_receipts':receipts},ensure_ascii=False,indent=2))
