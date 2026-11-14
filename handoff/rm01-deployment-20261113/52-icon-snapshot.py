from api import api
import pathlib,json,hashlib,subprocess,sys
root=pathlib.Path(__file__).parent;cid='6a5b5091-00be-4bf3-90cf-303160876c4a';ssh=['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99']
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
code="""import pathlib,hashlib,json
p=pathlib.Path('/app/data/plugins');h=p/'installed/hermes'
print(json.dumps({'plugin_config_sha256':hashlib.sha256((p/'config.json').read_bytes()).hexdigest(),'hermes_nonicon':{str(f.relative_to(h)):hashlib.sha256(f.read_bytes()).hexdigest() for f in h.rglob('*') if f.is_file() and f.name!='icon.png'},'installed_icon_sha256':hashlib.sha256((h/'icon.png').read_bytes()).hexdigest()}))"""
import shlex
plugin=json.loads(subprocess.check_output(ssh+['docker exec chatraw python -c '+shlex.quote(code)],text=True));container=json.loads(subprocess.check_output(ssh+['docker inspect chatraw'],text=True))[0];messages=api('GET',f'/api/chats/{cid}/messages')
out={'plugin':plugin,'models_hash':digest(api('GET','/api/models')),'settings_hash':digest(api('GET','/api/settings')),'user_chat':{'id':cid,'messages_hash':digest(messages),'message_count':len(messages),'binding':api('GET',f'/api/chats/{cid}/agent')},'unknown':api('GET','/api/agents/runs/e05b8525931c4d1585cae79770c7be3d'),'native_pids':subprocess.check_output(ssh+['systemctl show -p MainPID --value chatraw-runner chatraw-hermes'],text=True).split(),'container':{'id':container['Id'],'image':container['Image'],'mounts':container['Mounts']}}
(root/f'52-icon-{sys.argv[1]}.json').write_text(json.dumps(out,indent=2));print(json.dumps({'stage':sys.argv[1],'message_count':len(messages),'native_pids':out['native_pids'],'plugin':plugin}))
