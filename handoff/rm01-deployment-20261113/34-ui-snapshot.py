from api import api
import hashlib,json,pathlib,subprocess,sys
root=pathlib.Path(__file__).parent;cid='6a5b5091-00be-4bf3-90cf-303160876c4a'
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
messages=api('GET',f'/api/chats/{cid}/messages');chats=api('GET','/api/chats');chat=next(c for c in chats if c['id']==cid)
ssh=['ssh','-S','/tmp/chatraw-rm01-control.sock','-o','BatchMode=yes','rm01@10.10.99.99']
container=json.loads(subprocess.check_output(ssh+['docker inspect chatraw'],text=True))[0]
out={'user_chat_id':cid,'chat_metadata_hash':digest(chat),'messages_hash':digest(messages),'message_count':len(messages),'message_ids':[m['id'] for m in messages],'binding':api('GET',f'/api/chats/{cid}/agent'),'unknown_run':api('GET','/api/agents/runs/e05b8525931c4d1585cae79770c7be3d'),'models_hash':digest(api('GET','/api/models')),'settings_hash':digest(api('GET','/api/settings')),'container':{'id':container['Id'],'image':container['Image'],'mounts':container['Mounts']},'runner_hermes_pids':subprocess.check_output(ssh+['systemctl show -p MainPID --value chatraw-runner chatraw-hermes'],text=True).split()}
(root/f'34-ui-{sys.argv[1]}.json').write_text(json.dumps(out,indent=2));print(json.dumps({'stage':sys.argv[1],'messages':len(messages),'pids':out['runner_hermes_pids'],'container':container['Id']}))
