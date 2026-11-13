#!/usr/bin/env bash
set -euo pipefail
sudo -n python3 - <<'PY'
import json, pathlib, os, pwd
root=pathlib.Path('/var/lib/chatraw-runner'); uid=pwd.getpwnam('rm01').pw_uid; gid=pwd.getpwnam('rm01').pw_gid
base='http://10.10.99.98:58000'; model='RM-01 VLM'
def write(path, content, mode=0o600):
 p=pathlib.Path(path); p.write_text(content); p.chmod(mode); os.chown(p,uid,gid)
config=json.loads(pathlib.Path('/etc/chatraw-runner/config.json').read_text())
config['agents']['pi']['executable']='/opt/chatraw-agents/pi/node_modules/.bin/pi'
config['agents']['hermes']={'executable':'/opt/chatraw-agents/hermes/source/.venv/bin/hermes','home':str(root/'hermes-home')}
write('/etc/chatraw-runner/config.json',json.dumps(config,indent=2)+'\n',0o640)
write(root/'codex-home/config.toml','''model = "RM-01 VLM"
model_provider = "rm01"
[model_providers.rm01]
name = "RM-01 local vLLM"
base_url = "http://10.10.99.98:58000/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
[model_providers.rm01.capabilities]
remote_compaction = "unsupported"
''')
write(root/'pi-home/models.json',json.dumps({'providers':{'rm01':{'baseUrl':base+'/v1','api':'openai-completions','apiKey':'local-no-auth-placeholder','models':[{'id':model,'name':model,'input':['text','image'],'contextWindow':262144,'maxTokens':8192}]}}},indent=2))
write(root/'pi-home/settings.json',json.dumps({'retry':{'enabled':False}}))
write(root/'hermes-home/config.yaml','''model:
  provider: custom
  default: "RM-01 VLM"
  base_url: "http://10.10.99.98:58000/v1"
  supports_vision: true
agent:
  image_input_mode: native
auxiliary:
  title_generation:
    enabled: false
plugins:
  auto_update_check_hours: 0
''')
env={
 'PATH':'/opt/chatraw-agents/codex/node_modules/.bin:/opt/chatraw-agents/pi/node_modules/.bin:/opt/chatraw-agents/hermes/source/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
 'NO_PROXY':'127.0.0.1,localhost,10.10.99.98,10.10.99.99','no_proxy':'127.0.0.1,localhost,10.10.99.98,10.10.99.99',
 'CODEX_HOME':str(root/'codex-home'),'CLAUDE_CONFIG_DIR':str(root/'claude-home'),'PI_CODING_AGENT_DIR':str(root/'pi-home'),'HERMES_HOME':str(root/'hermes-home'),
 'HERMES_GATEWAY_LOCK_DIR':str(root/'hermes-locks'),
 'ANTHROPIC_BASE_URL':base,'ANTHROPIC_API_KEY':'local-no-auth-placeholder',
 'DEEPSEEK_BASE_URL':base+'/v1','DEEPSEEK_API_KEY':'local-no-auth-placeholder',
 'OPENAI_BASE_URL':base+'/v1','OPENAI_API_KEY':'local-no-auth-placeholder',
 'DISABLE_TELEMETRY':'1','DISABLE_ERROR_REPORTING':'1','DISABLE_NONESSENTIAL_MODEL_CALLS':'1','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1',
 'ANTHROPIC_DEFAULT_HAIKU_MODEL':model,'ANTHROPIC_DEFAULT_SONNET_MODEL':model,'ANTHROPIC_DEFAULT_OPUS_MODEL':model,
 'PYTHONUNBUFFERED':'1','NO_COLOR':'1'
}
write('/etc/chatraw-runner/environment','\n'.join(f'{k}="{v}"' for k,v in env.items())+'\n',0o640)
unit=pathlib.Path('/etc/systemd/system/chatraw-hermes.service')
assert not unit.exists(),'Refusing to overwrite existing Hermes unit'
unit.write_text('''[Unit]
Description=ChatRaw dedicated Hermes native Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=rm01
WorkingDirectory=/var/lib/chatraw-runner/hermes-home
EnvironmentFile=/etc/chatraw-runner/environment
ExecStart=/opt/chatraw-agents/hermes/source/.venv/bin/hermes gateway run
Restart=on-failure
RestartSec=5
TimeoutStopSec=60
UMask=0077

[Install]
WantedBy=multi-user.target
''');unit.chmod(0o644)
print('Configured five native Agent homes and local model endpoints; no credentials printed')
PY
sudo -n systemctl daemon-reload
