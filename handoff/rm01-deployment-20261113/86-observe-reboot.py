import socket,time,json,pathlib,datetime,urllib.request
p=pathlib.Path(__file__).parent;ports=[22,51111,59090,59009,2049,445,139];previous=None;rows=[];start=time.monotonic();saw_down=False;opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(90):
 state={}
 for port in ports:
  try:
   with socket.create_connection(('10.10.99.99',port),timeout=0.5):state[str(port)]=True
  except OSError:state[str(port)]=False
 if not state['22'] or not state['51111']:saw_down=True
 ready=False
 if state['51111']:
  try:
   with opener.open('http://10.10.99.99:51111/ready',timeout=2) as r:ready=json.load(r).get('status')=='ready'
  except Exception:pass
 snapshot={'ports':state,'chatraw_ready':ready}
 if snapshot!=previous:
  row={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed':round(time.monotonic()-start,2),**snapshot};rows.append(row);(p/'86-reboot-network-observations.json').write_text(json.dumps({'saw_down':saw_down,'changes':rows},indent=2));print(json.dumps(row),flush=True);previous=snapshot
 if saw_down and all(state.values()) and ready:break
 time.sleep(2)
print(json.dumps({'observation_complete':True,'saw_down':saw_down,'elapsed':round(time.monotonic()-start,2)}),flush=True)
