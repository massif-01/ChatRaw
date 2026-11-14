"""No root, Docker daemon, downloads or model calls required."""
import importlib.util
import http.server
import threading
import urllib.error
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('chatraw_setup', Path(__file__).with_name('setup.py'))
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.paths = {key: self.root / key for key in ('CODE', 'CONFIG', 'DATA', 'UNIT')}
        self.mock_paths = patch.multiple(setup, **self.paths)
        self.mock_paths.start()

    def tearDown(self):
        self.mock_paths.stop()
        self.tmp.cleanup()

    def test_fresh_and_partial_install(self):
        self.assertEqual(setup.runner_state(), 'new')
        self.paths['DATA'].mkdir()
        sentinel = self.paths['DATA'] / 'old-session'
        sentinel.write_text('keep')
        with self.assertRaisesRegex(RuntimeError, '未完成'):
            setup.runner_state()
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_complete_install_is_preserved(self):
        for key in ('CODE', 'CONFIG', 'DATA'):
            self.paths[key].mkdir()
        (self.paths['CODE'] / 'venv/bin').mkdir(parents=True)
        for path in (self.paths['CODE'] / 'venv/bin/python', self.paths['CONFIG'] / 'config.json',
                     self.paths['CONFIG'] / 'token', self.paths['UNIT']):
            path.write_text('preserve')
            path.chmod(0o600)
        before = {p: (p.read_bytes(), p.stat().st_mode) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(setup.runner_state(), 'existing')
        self.assertEqual(setup.runner_state(), 'existing')
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mode) for p in before})

    def test_exclusive_creation_refuses_files_and_symlinks(self):
        target = self.root / 'credentials'
        target.write_text('secret')
        link = self.root / 'link'
        link.symlink_to(target)
        dangling = self.root / 'dangling'
        dangling.symlink_to(self.root / 'absent')
        for path in (target, link, dangling):
            with self.assertRaises(FileExistsError):
                setup.create_file(path, 'replacement')
        self.assertEqual(target.read_text(), 'secret')
        self.assertFalse((self.root / 'absent').exists())

    def test_existing_container_never_recreated(self):
        with patch.object(setup, 'capture', return_value='chatraw'), patch.object(setup, 'free_port') as port:
            self.assertEqual(setup.docker_state(), 'existing')
            port.assert_not_called()

    def test_orphan_volume_stops_before_deploy(self):
        with patch.object(setup, 'capture', side_effect=['', 'chatraw_chatraw_data']):
            with self.assertRaisesRegex(RuntimeError, '已有.*数据卷'):
                setup.docker_state()

    def test_default_confirmation_is_no(self):
        with patch('builtins.input', return_value=''):
            self.assertFalse(setup.yes('安装'))

    def test_cancel_has_no_install_calls(self):
        account = type('Account', (), {'pw_name': 'user', 'pw_uid': 1000})()
        with patch.object(setup.sys, 'argv', ['setup.py', 'new']), \
             patch.object(setup.sys, 'platform', 'linux'), \
             patch.object(setup.os, 'geteuid', return_value=0), \
             patch.object(setup.sys.stdin, 'isatty', return_value=True), \
             patch.object(setup.shutil, 'which', return_value='/usr/bin/tool'), \
             patch.object(setup.Path, 'exists', return_value=True), \
             patch.object(setup, 'run'), \
             patch.object(setup, 'capture', return_value='{"OSType":"linux","OperatingSystem":"Ubuntu"}'), \
             patch.object(setup, 'runner_state', return_value='new'), \
             patch.object(setup, 'docker_state', return_value='new'), \
             patch.object(setup, 'free_port'), \
             patch.object(setup.pwd, 'getpwnam', return_value=account), \
             patch('builtins.input', side_effect=['user', 'n']), \
             patch.object(setup, 'install_runner') as install:
            setup.main()
            install.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_new_container_appearing_during_confirmation_is_preserved(self):
        with patch.object(setup.sys, 'argv', ['setup.py', 'new']), \
             patch.object(setup.sys, 'platform', 'linux'), \
             patch.object(setup.os, 'geteuid', return_value=0), \
             patch.object(setup.sys.stdin, 'isatty', return_value=True), \
             patch.object(setup.shutil, 'which', return_value='/usr/bin/tool'), \
             patch.object(setup.Path, 'exists', return_value=True), \
             patch.object(setup, 'run') as run, \
             patch.object(setup, 'capture', return_value='{"OSType":"linux","OperatingSystem":"Ubuntu"}'), \
             patch.object(setup, 'runner_state', return_value='existing'), \
             patch.object(setup, 'inspect_existing_runner'), \
             patch.object(setup, 'docker_state', side_effect=['new', 'existing']), \
             patch('builtins.input', return_value='y'), \
             patch.object(setup, 'install_runner') as install:
            with self.assertRaisesRegex(RuntimeError, '安装期间出现'):
                setup.main()
            install.assert_not_called()
            self.assertFalse(any('up' in call.args[0] for call in run.call_args_list))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_agent_plan_does_not_copy_keys_or_install(self):
        account = type('Account', (), {'pw_name': 'user', 'pw_dir': '/home/user'})()
        with patch.object(setup, 'discover', return_value=''), patch.object(setup, 'yes', return_value=False):
            self.assertEqual(setup.plan_agents(account), ({}, {}, []))

    def test_new_install_modes_and_repeat_preservation(self):
        account = type('Account', (), {'pw_name': 'user', 'pw_uid': os.getuid(), 'pw_gid': os.getgid()})()
        def fake_run(args, **kwargs):
            if '-m' in args and 'venv' in args:
                (self.paths['CODE'] / 'venv/bin').mkdir(parents=True)
                (self.paths['CODE'] / 'venv/bin/python').touch()
        source = self.root / 'source'
        (source / 'agent_runner').mkdir(parents=True, mode=0o700)
        (source / 'agent_runner/module.py').write_text('# test')
        (source / 'agent_runner/module.py').chmod(0o600)
        (source / 'deploy').mkdir()
        (source / 'deploy/chatraw-runner.service').write_text('User=@RUNNER_USER@')
        previous = os.umask(0o077)
        try:
            with patch.object(setup, 'SOURCE', source), \
                 patch.object(setup, 'run', side_effect=fake_run), \
                 patch.object(setup.os, 'chown'), patch.object(setup.os, 'fchown'), \
                 patch.object(setup, 'check_runner_health'):
                setup.install_runner(account, {}, {}, [])
            restored = os.umask(0o077)
            self.assertEqual(restored, 0o077)
            expected = {self.paths['CODE'] / 'agent_runner': 0o755,
                        self.paths['CODE'] / 'agent_runner/module.py': 0o644,
                        self.paths['CODE']: 0o755, self.paths['CONFIG']: 0o750,
                        self.paths['DATA']: 0o700, self.paths['CODE'] / 'venv/bin': 0o755,
                        self.paths['CONFIG'] / 'config.json': 0o640,
                        self.paths['CONFIG'] / 'environment': 0o640,
                        self.paths['CONFIG'] / 'token': 0o600, self.paths['UNIT']: 0o644}
            for path, mode in expected.items():
                self.assertEqual(path.stat().st_mode & 0o777, mode, str(path))
            self.assertEqual((source / 'agent_runner').stat().st_mode & 0o777, 0o700)
            self.assertEqual((source / 'agent_runner/module.py').stat().st_mode & 0o777, 0o600)
            before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
            with self.assertRaises(FileExistsError):
                setup.install_runner(account, {}, {}, [])
            self.assertEqual(before, {p: p.read_bytes() for p in before})
        finally:
            os.umask(previous)

    def test_failed_health_does_not_report_success(self):
        self.paths['CONFIG'].mkdir()
        (self.paths['CONFIG'] / 'token').write_text('test-token')
        with patch.object(setup, 'local_json', side_effect=OSError('offline')), \
             patch.object(setup.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'Runner 未通过'):
                setup.check_runner_health()
            with self.assertRaisesRegex(RuntimeError, '网页尚未就绪'):
                setup.summarize('new')

    def test_runner_health_checks_identity_and_uses_token(self):
        self.paths['CONFIG'].mkdir()
        (self.paths['CONFIG'] / 'token').write_text('test-token')
        with patch.object(setup, 'local_json', return_value={'service': 'other'}), \
             patch.object(setup.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                setup.check_runner_health()
        with patch.object(setup, 'local_json', return_value={'service': 'chatraw-agent-runner'}) as request:
            setup.check_runner_health()
            request.assert_called_once_with('http://127.0.0.1:51112/v1/health', 'test-token')

    def test_path_with_spaces_and_quotes(self):
        path = self.root / 'Agent Home'
        path.mkdir()
        account = type('Account', (), {'pw_name': 'user'})()
        with patch('builtins.input', side_effect=['/bad"path', str(path)]), \
             patch.object(setup, 'account_access', return_value=True):
            self.assertEqual(setup.absolute_path('home', '', account), str(path))

    def test_existing_native_codex_can_skip_node(self):
        account = type('Account', (), {'pw_name': 'user', 'pw_dir': '/home/user'})()
        with patch.object(setup, 'discover', return_value=''), \
             patch.object(setup, 'yes', side_effect=[True, False, False, False, False, False]), \
             patch.object(setup, 'absolute_path', side_effect=['/opt/codex', '/home/user/.codex']) as paths:
            agents, environment, sdk = setup.plan_agents(account)
        self.assertEqual(paths.call_count, 2)
        self.assertEqual(environment['CODEX_HOME'], '/home/user/.codex')
        self.assertTrue(environment['PATH'].startswith('/opt:'))
        self.assertEqual((agents, sdk), ({}, []))

    def test_docker_target_ignores_remote_environment(self):
        with patch.dict(os.environ, {'DOCKER_HOST': 'tcp://remote:2375',
                                     'DOCKER_CONTEXT': 'remote', 'DOCKER_TLS': '1', 'DOCKER_TLS_VERIFY': '1',
                                     'DOCKER_CERT_PATH': '/private/certs'}), \
             patch.object(setup.subprocess, 'run') as execute:
            setup.run(['docker', 'info'])
        args, kwargs = execute.call_args
        self.assertEqual(args[0], ['docker', '--host', 'unix:///var/run/docker.sock', 'info'])
        for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
            self.assertNotIn(key, kwargs['env'])

    def test_home_requires_read_write_and_search_access(self):
        path = self.root / 'home'
        path.mkdir()
        account = type('Account', (), {'pw_name': 'user'})()
        with patch('builtins.input', side_effect=[str(path), str(path)]), \
             patch.object(setup, 'account_access', side_effect=[True, True, False, True, True, True]) as access:
            self.assertEqual(setup.absolute_path('home', '', account), str(path))
        self.assertEqual([call.args[2] for call in access.call_args_list], ['-r', '-w', '-x'] * 2)

    def test_health_bypasses_proxy_and_refuses_redirect(self):
        seen = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, self.headers.get('Authorization')))
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/target')
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"service":"chatraw-agent-runner"}')

            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with patch.dict(os.environ, {'HTTP_PROXY': 'http://127.0.0.1:1',
                                         'http_proxy': 'http://127.0.0.1:1',
                                         'NO_PROXY': '', 'no_proxy': ''}):
                self.assertEqual(setup.local_json(origin, 'test-token')['service'], 'chatraw-agent-runner')
                with self.assertRaises(urllib.error.HTTPError):
                    setup.local_json(origin + '/redirect', 'test-token')
            self.assertEqual(seen, [('/', 'Bearer test-token'), ('/redirect', 'Bearer test-token')])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
