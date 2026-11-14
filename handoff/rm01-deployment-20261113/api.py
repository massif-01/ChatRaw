import json, urllib.request, urllib.error
BASE='http://10.10.99.99:51111'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def api(method,path,body=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Origin':BASE,'Content-Type':'application/json'})
 try:
  with opener.open(req,timeout=90) as r:return json.load(r)
 except urllib.error.HTTPError as e: raise RuntimeError(f'{method} {path}: {e.code} {e.read().decode()}')
if __name__=='__main__':
 for agent in ['codex','claude','pi','deepseek','hermes']:
  print(agent,'install',api('POST','/api/plugins/install-bundled',{'plugin_id':agent}),flush=True)
  settings={'model':'RM-01 VLM'}
  if agent=='pi':settings['provider']='rm01'
  if agent=='hermes':settings['provider']='custom'
  print(agent,'settings',api('POST',f'/api/plugins/{agent}/settings',{'settings':settings}),flush=True)
  print(agent,'health',api('GET',f'/api/agents/{agent}/health'),flush=True)
