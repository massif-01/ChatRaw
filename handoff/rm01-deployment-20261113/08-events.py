from api import opener,BASE
import json,urllib.request,pathlib,sys
agent=sys.argv[1]; root=pathlib.Path(__file__).parent
r=json.loads((root/f'07-{agent}.json').read_text());run=r['submitted']['run_id']
req=urllib.request.Request(BASE+f'/api/agents/runs/{run}/events',headers={'Origin':BASE})
with opener.open(req,timeout=30) as resp,(root/f'08-{agent}-events.ndjson').open('w') as out:
 for line in resp:
  if not line.strip():continue
  event=json.loads(line);out.write(json.dumps(event)+'\n');out.flush()
  if event.get('type') in ('tool_start','tool_end','completed','failed','error'):print(json.dumps(event))
print('Event stream archived')
