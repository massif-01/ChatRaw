import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('CHATRAW_TEST_ASSET_DIR', ROOT / 'backend' / 'static')).resolve()
MARKET = ROOT / 'Plugins' / 'Plugin_market'
ids = ['hermes', 'codex', 'claude', 'pi', 'deepseek']
installed = {}
for name in ['markdown-enhancer', 'mindmap-renderer', 'enhanced-export', 'context-compressor', 'skill-manager']:
    installed[name] = True
chats = {}
messages = {}
bindings = {}
runs = {}
admissions = {}
settings = {}
logs = []
events = threading.Condition()
LONG = 'Keep generated files within the workspace. ' * 7
MARKDOWN = '# Workspace report\n\nThis paragraph remains stable.\n\n- First item\n- **Second** item\n\n| Item | Result |\n| --- | --- |\n| Tests | Passed |\n\n$$E = mc^2$$\n\n```python\nprint("ready")\n```\n\n```markmap\n# Test map\n- Test node\n```\n\n[Unsafe](javascript&#58;alert(1)) <img src=x onerror=alert(1)>'
APPROVAL = {
    'interaction_id': 'approval-1', 'kind': 'approval', 'title': 'Review file change',
    'detail': '## Plan\n\n1. Update the requested file.\n2. Run local checks.\n\n<script>window.fixtureUnsafe = true</script>',
    'presentation': 'plan', 'allow_cancel': True, 'expires_at': None,
    'operation': {'tool': 'write_file', 'command': 'test -f report.txt', 'cwd_label': 'ChatRaw fixture', 'paths': ['report.txt']},
    'decisions': [{'id': 'permit', 'label': 'Allow this change', 'scope': 'Current operation'},
                  {'id': 'reject', 'label': 'Reject the change'}],
}
QUESTIONS = {
    'interaction_id': 'questions-1', 'kind': 'question', 'title': 'Choose how to run the checks',
    'detail': 'Confirm the scope of this simulated run.', 'allow_cancel': True, 'expires_at': None,
    'questions': [
        {'id': 'single', 'text': 'Choose the test scope', 'type': 'single', 'required': True, 'allow_custom': True,
         'options': [{'id': 'fast', 'label': 'Quick checks', 'description': LONG, 'recommended': True},
                     {'id': 'full', 'label': 'Full suite'}]},
        {'id': 'multi', 'text': 'Select outputs', 'type': 'multi', 'required': True, 'allow_custom': False,
         'options': [{'id': 'log', 'label': 'Log'}, {'id': 'report', 'label': 'Report'}]},
        {'id': 'text', 'text': 'Add a short note', 'type': 'text', 'required': True, 'allow_custom': False, 'options': []},
    ],
}

def binding(chat):
    return bindings.get(chat, {'chat_id': chat, 'agent_id': None, 'session_id': None, 'workspace': None,
                               'active_run_id': None, 'last_run_id': None})

def add_event(run, kind, data):
    with events:
        run['events'].append({'schema_version': 1, 'run_id': run['run_id'], 'session_id': run['session_id'],
                              'seq': len(run['events']) + 1, 'timestamp': datetime.now(timezone.utc).isoformat(),
                              'type': kind, 'data': data})
        events.notify_all()

def status(run, value):
    with events:
        run['status'] = value
        add_event(run, 'status', {'status': value})

def interact(run, interaction):
    with events:
        run['interactions'][interaction['interaction_id']] = interaction
        add_event(run, 'interaction_requested', interaction)

def finish(run, value, final_text):
    with events:
        run['status'] = value
        for key in list(run['interactions']):
            del run['interactions'][key]
            add_event(run, 'interaction_resolved', {'interaction_id': key, 'outcome': 'invalidated'})
        add_event(run, 'done', {'status': value, 'final_text': final_text})
        chat = run['chat_id']
        messages[chat].append({'id': 'assistant-' + run['run_id'], 'run_id': run['run_id'], 'role': 'assistant', 'content': final_text})
        binding(chat)['active_run_id'] = None

def demo_run(run, message):
    status(run, 'running')
    for chunk in ['# Workspace report\n\n', 'This paragraph remains stable.', '\n\n- First item', '\n- **Second** item']:
        if run['status'] != 'running':
            return
        add_event(run, 'text_delta', {'text': chunk})
        time.sleep(.27)
    add_event(run, 'tool_started', {'tool_call_id': 'tool-1', 'name': 'inspect', 'title': 'Inspect workspace'})
    add_event(run, 'tool_completed', {'tool_call_id': 'tool-1', 'name': 'inspect', 'status': 'completed', 'duration_ms': 28})
    if message == '/compact':
        finish(run, 'completed', '')
        return
    if message == 'expire':
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=3)).isoformat()
        status(run, 'waiting_approval')
        interact(run, {**APPROVAL, 'expires_at': expiry})
        time.sleep(4.4)
        finish(run, 'interrupted', '')
        return
    status(run, 'waiting_input')
    interact(run, QUESTIONS)
    interact(run, {**APPROVAL, 'interaction_id': 'parallel-1', 'title': 'Confirm test prerequisites'})

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        pass

    def reply(self, data, code=200, mime='application/json', headers=None):
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except BrokenPipeError:
            pass

    def json_body(self):
        size = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(size)
        return json.loads(data) if data else {}

    def asset(self, path):
        path = path.resolve()
        if not (path.is_relative_to(ROOT) or path.is_relative_to(STATIC)) or not path.is_file():
            return self.reply({'error': 'File missing'}, 404)
        mimes = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.png': 'image/png', '.woff2': 'font/woff2'}
        return self.reply(path.read_bytes(), mime=mimes.get(path.suffix, 'application/octet-stream'))

    def manifest(self, plugin):
        data = json.loads((MARKET / plugin / 'manifest.json').read_text())
        return {**data, 'enabled': installed.get(plugin, False), 'settings_values': settings.get(plugin, {})}

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        parts = path.strip('/').split('/')
        if path == '/':
            return self.asset(ROOT / 'backend/static/index.html')
        if path == '/api/settings':
            return self.reply({'chat_settings': {'stream': True, 'system_prompt': 'fixture system prompt'},
                               'rag_settings': {}, 'ui_settings': {'theme_mode': 'light'}})
        if path == '/api/settings/logo':
            return self.reply({'logo_data': ''})
        if path == '/api/models':
            return self.reply([{'type': 'chat', 'name': 'Fixture model', 'supports_vision': False}])
        if path in ('/api/documents', '/api/skills'):
            return self.reply([])
        if path == '/api/chats':
            return self.reply(list(reversed(chats.values())))
        if len(parts) == 4 and parts[:2] == ['api', 'chats']:
            chat = parts[2]
            return self.reply(binding(chat) if parts[3] == 'agent' else messages[chat])
        if path == '/api/plugins':
            return self.reply([self.manifest(plugin) for plugin in installed])
        if path == '/api/plugins/market':
            return self.asset(MARKET / 'index.json')
        if len(parts) >= 4 and parts[:2] == ['api', 'plugins']:
            if parts[2] == 'market':
                return self.asset(MARKET / parts[3] / 'icon.png')
            plugin, item = parts[2:4]
            if item == 'manifest':
                return self.reply(self.manifest(plugin))
            return self.asset(MARKET / plugin / ('icon.png' if item == 'icon' else '/'.join(parts[3:])))
        if path == '/api/agents':
            agents = []
            for agent in ids:
                agents.append({'id': agent, 'name': self.manifest(agent)['name']['en'], 'installed': agent in installed,
                               'enabled': installed.get(agent, False), 'availability': 'ready', 'reason': '',
                               'capabilities': {'cancel': True, 'compact': agent != 'deepseek', 'images': agent != 'pi', 'files': True},
                               'settings_revision': 1, 'settings_schema': {'type': 'object', 'additionalProperties': False,
                                   'properties': {'model': {'type': 'string', 'minLength': 1},
                                                  'level': {'type': 'string', 'enum': ['balanced', 'high']},
                                                  'trace': {'type': 'boolean'},
                                                  'budget': {'type': 'integer', 'minimum': 1, 'maximum': 12}}}})
            return self.reply({'agents': agents})
        if path == '/api/agents/workspaces':
            return self.reply({'workspaces': [{'id': 'chatraw-fixture', 'label': 'ChatRaw fixture'}]})
        if len(parts) == 4 and parts[:2] == ['api', 'agents'] and parts[3] == 'health':
            return self.reply({'agent_id': parts[2], 'availability': 'ready', 'version': 'fixture-v1', 'reason': 'Contract fixture',
                               'models': [{'id': 'fixture-native', 'name': 'Fixture native model'}],
                               'checks': {'program': 'passed', 'protocol': 'passed', 'authentication': 'unknown', 'model_request': 'not_checked'}})
        if path == '/api/agents/runs':
            query = parse_qs(parsed.query)
            run = admissions.get((query['chat_id'][0], query['client_request_id'][0]))
            return self.reply({'admission': 'accepted' if run else 'not_found', 'run': run and {'run_id': run['run_id']}})
        if len(parts) >= 4 and parts[:3] == ['api', 'agents', 'runs']:
            run = runs[parts[3]]
            if len(parts) == 4:
                with events:
                    result = {key: run[key] for key in ('run_id', 'chat_id', 'session_id', 'status')}
                    result['last_seq'] = len(run['events'])
                    result['interactions'] = list(run['interactions'].values())
                return self.reply(result)
            if parts[4] == 'events':
                after = int(parse_qs(parsed.query).get('after', [0])[0])
                return self.stream_run(run, after)
        if path.startswith('/api/agents/artifacts/'):
            return self.reply(b'fixture artifact', mime='text/plain', headers={'Content-Disposition': 'attachment; filename="report.txt"'})
        if path == '/fixture/logs':
            return self.reply(logs)
        if path == '/fixture/state':
            return self.reply({'runs': len(runs), 'chats': len(chats)})
        if path[1:] in ('app.min.js', 'styles.min.css'):
            return self.asset(STATIC / path[1:])
        return self.asset(ROOT / 'backend/static' / path[1:])

    def stream_run(self, run, after):
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        first = not run.get('streamed')
        run['streamed'] = True
        if after:
            logs.append(('reconnect', run['run_id'], after))
        try:
            if after:
                self.wfile.write((json.dumps(run['events'][after-1]) + '\n').encode())
                self.wfile.flush()
            while True:
                with events:
                    events.wait_for(lambda: len(run['events']) > after, timeout=10)
                    available = run['events'][after:]
                if not available:
                    self.wfile.write(b'\n')
                    self.wfile.flush()
                for item in available:
                    self.wfile.write((json.dumps(item) + '\n').encode())
                    self.wfile.flush()
                    after += 1
                    if item['type'] == 'done' or first and after == 2:
                        return
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_PUT(self):
        chat = self.path.split('/')[3]
        data = self.json_body()
        logs.append(('bind', chat, data))
        if messages[chat] or binding(chat)['active_run_id']:
            return self.reply({'error': 'Chat already has messages'}, 409)
        project = data['workspace'].get('id')
        bindings[chat] = {'chat_id': chat, 'agent_id': data['agent_id'], 'session_id': 'session-' + chat,
                          'workspace': {'kind': data['workspace']['kind'], 'id': project or chat,
                                        'label': 'ChatRaw fixture' if project else 'Managed workspace'},
                          'active_run_id': None, 'last_run_id': None}
        self.reply(bindings[chat])

    def do_POST(self):
        path = self.path
        parts = path.strip('/').split('/')
        if path == '/api/agents/attachments':
            raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            logs.append(('attachment', raw.decode(errors='replace')))
            return self.reply({'attachment_id': 'fixture-file', 'name': 'input.txt', 'mime_type': 'text/plain', 'size': 4})
        data = self.json_body()
        logs.append(('post', path, data))
        if path == '/api/chats':
            chat = 'chat-' + str(len(chats) + 1)
            chats[chat] = {'id': chat, 'title': 'Chat ' + str(len(chats) + 1)}
            messages[chat] = []
            return self.reply(chats[chat])
        if path == '/api/plugins/install-bundled':
            plugin = data['plugin_id']
            installed[plugin] = True
            return self.reply({'success': True, 'plugin_id': plugin, 'manifest': self.manifest(plugin)})
        if len(parts) == 4 and parts[:2] == ['api', 'plugins']:
            if parts[3] == 'toggle':
                installed[parts[2]] = data['enabled']
                return self.reply({'success': True})
            if parts[3] == 'settings':
                settings[parts[2]] = data['settings']
                return self.reply({'success': True})
        if path == '/api/chat':
            if data['chat_id']:
                chat = data['chat_id']
            else:
                chat = 'chat-' + str(len(chats) + 1)
                chats[chat] = {'id': chat, 'title': 'Ordinary fixture'}
                messages[chat] = []
            messages[chat] += [{'role': 'user', 'content': data['message']}, {'role': 'assistant', 'content': MARKDOWN}]
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-ndjson')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            for part in [{'chat_id': chat, 'thinking': 'Fixture reasoning'}, {'content': MARKDOWN[:48]}, {'content': MARKDOWN[48:]}]:
                self.wfile.write((json.dumps(part) + '\n').encode())
                self.wfile.flush()
                time.sleep(.4)
            return
        if path == '/api/agents/runs' or len(parts) == 5 and parts[:3] == ['api', 'agents', 'sessions']:
            chat = data.get('chat_id') or parts[3].removeprefix('session-')
            message = data.get('message', '/compact')
            run_id = 'run-' + str(uuid.uuid4())[:8]
            if binding(chat)['active_run_id']:
                return self.reply({'error': 'Already running'}, 409)
            run = {'run_id': run_id, 'chat_id': chat, 'session_id': binding(chat)['session_id'],
                   'status': 'queued', 'events': [], 'interactions': {}}
            runs[run_id] = run
            admissions[(chat, data['client_request_id'])] = run
            binding(chat).update(active_run_id=run_id, last_run_id=run_id)
            messages[chat].append({'id': 'user-' + run_id, 'run_id': run_id, 'role': 'user', 'content': message})
            threading.Thread(target=demo_run, args=(run, message), daemon=True).start()
            if 'lost-admission' in message:
                return self.reply({'error': 'Response lost after admission'}, 503)
            return self.reply({key: run[key] for key in ('run_id', 'chat_id', 'session_id', 'status')}, 202)
        if len(parts) >= 5 and parts[:3] == ['api', 'agents', 'runs']:
            run = runs[parts[3]]
            if parts[4] == 'cancel':
                status(run, 'stopping')
                threading.Timer(.4, finish, (run, 'cancelled', '')).start()
                return self.reply({'run_id': run['run_id'], 'status': 'stopping'})
            key = parts[5]
            with events:
                interaction = run['interactions'].get(key)
                expiry = interaction and interaction.get('expires_at')
                if not interaction or (expiry and datetime.fromisoformat(expiry) <= datetime.now(timezone.utc)):
                    return self.reply({'error': 'Interaction expired'}, 409)
                del run['interactions'][key]
                add_event(run, 'interaction_resolved', {'interaction_id': key, 'outcome': 'answered', 'answer_summary': 'Fixture received response'})
                if not run['interactions']:
                    status(run, 'running')
                    add_event(run, 'artifact', {'artifact_id': 'artifact-report', 'name': 'report.txt', 'mime_type': 'text/plain', 'size': 16})
                    add_event(run, 'usage', {'input_tokens': 52, 'output_tokens': 19})
                    finish(run, 'completed', MARKDOWN)
            return self.reply({'success': True})
        return self.reply({'error': 'Unknown POST'}, 404)

    def do_DELETE(self):
        parts = self.path.strip('/').split('/')
        if parts[:2] == ['api', 'plugins']:
            installed.pop(parts[2], None)
            return self.reply({'success': True})
        if parts[:2] == ['api', 'chats']:
            if binding(parts[2])['active_run_id']:
                return self.reply({'error': 'Run active'}, 409)
            chats.pop(parts[2], None)
            return self.reply({'success': True})
        self.reply({'error': 'Unknown DELETE'}, 404)

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
print(f'PORT {server.server_port}', flush=True)
server.serve_forever()
