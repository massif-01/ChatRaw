from compression import zstd
import pathlib,json,sqlite3
root=pathlib.Path('/var/lib/chatraw-runner/deepseek/session-2c63be8b22744b3cb0c81413a51f6aad')
headers=[]
for p in root.rglob('session.v4.jsonl.zstd'):
 with zstd.open(p,'rt') as f:
  for l in f:
   o=json.loads(l)
   if o.get('type')=='request/header':headers.append({'seq':o['seq'],'time':o['time'],'config':o['data']['header']['config']})
processes=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
 try:
  cmd=(p/'cmdline').read_bytes().split(b'\0');exe=pathlib.Path(cmd[0].decode()).name
  if not exe.startswith('deepseek-harness-sdk-runtime'):continue
  cwd=str((p/'cwd').resolve());stat=(p/'stat').read_text().split()
  if cwd!='/var/lib/chatraw-runner/workspaces/14d1c7a3dbda4f3fad1a20a4b35d523f':continue
  processes.append({'pid':int(p.name),'starttime_ticks':stat[21],'executable':exe,'cwd':cwd})
 except (FileNotFoundError,PermissionError,IndexError):pass
c=sqlite3.connect('file:/var/lib/chatraw-runner/runner.db?mode=ro',uri=True)
binding=json.loads(c.execute("select binding from sessions where id='14d1c7a3dbda4f3fad1a20a4b35d523f'").fetchone()[0])
print(json.dumps({'headers':headers,'native_processes':processes,'binding':binding}))
