import importlib.util,pathlib,json
root=pathlib.Path(__file__).parent
path=pathlib.Path('/Users/massif/.codex/worktrees/9133/ChatRaw/docs/agent-platform/handoffs/D-field/verify.py');spec=importlib.util.spec_from_file_location('field_case',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
prior=json.loads((root/'73-codex-compat-compact/result.json').read_text());out=root/'74-codex-same-chat-image';out.mkdir()
api=module.Api('http://10.10.99.99:51111');case=module.Case(api,'codex','image',out,120);case.chat_id=prior['chat_id'];case.binding=api.json('GET',f'/api/chats/{case.chat_id}/agent');case.workspace=module.workspace_path(case.binding);case.report.update(chat_id=case.chat_id,binding=case.binding,same_chat_as_compact=True)
try:case.report['outcome']=case.image()
finally:case.save()
print(json.dumps({'outcome':case.report['outcome'],'image':case.report['image'],'chat_id':case.chat_id}),flush=True)
