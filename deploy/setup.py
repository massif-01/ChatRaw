#!/usr/bin/env python3
"""Interactive, create-only Linux setup. Never upgrades an existing deployment."""
import argparse
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

SOURCE = Path(__file__).resolve().parent.parent
CODE = Path('/opt/chatraw-runner')
CONFIG = Path('/etc/chatraw-runner')
DATA = Path('/var/lib/chatraw-runner')
UNIT = Path('/etc/systemd/system/chatraw-runner.service')
DOCKER_ENDPOINT = 'unix:///var/run/docker.sock'
BASE_PATH = '/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin'


def run(args, **kwargs):
    if str(args[0]) == 'docker':
        # CLI target is explicit and independent of the caller's remote context/TLS settings.
        environment = dict(kwargs.pop('env', os.environ))
        for name in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
            environment.pop(name, None)
        kwargs['env'] = environment
        args = ['docker', '--host', DOCKER_ENDPOINT, *args[1:]]
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def capture(args):
    return run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()


def ask(label, default=''):
    value = input(f'{label}' + (f' [{default}]' if default else '') + '：').strip()
    return value or default


def yes(label, default=False):
    while True:
        answer = ask(label + ('（Y/n）' if default else '（y/N）')).lower()
        if not answer:
            return default
        if answer in ('y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        print('请输入 y 或 n。')


def account_access(account, path, mode):
    return subprocess.run(['runuser', '-u', account.pw_name, '--', 'test', mode, str(path)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def absolute_path(label, default, account, executable=False):
    while True:
        path = Path(ask(label, default))
        if not path.is_absolute() or any(c in str(path) for c in '\n\r"\\%'):
            print('请填写绝对路径；路径不能包含换行、双引号、反斜杠或 %。')
            continue
        modes = ('-x',) if executable else ('-r', '-w', '-x')
        if (path.is_file() if executable else path.is_dir()) and all(
                account_access(account, path, mode) for mode in modes):
            return str(path)
        print(f'账户 {account.pw_name} 无法{"执行该文件" if executable else "读写并进入该目录"}。请修正路径或权限后再试。')


def discover(account, name):
    # Never execute the user's shell startup files as root.
    for directory in (Path(account.pw_dir) / '.local/bin', Path(account.pw_dir) / '.npm-global/bin',
                      Path('/usr/local/bin'), Path('/usr/bin')):
        path = directory / name
        if path.is_file() and account_access(account, path, '-x'):
            return str(path)
    return ''


def plan_agents(account):
    agents, environment, sdk = {}, {}, []
    print('\n只选择你要接入的 Agent；不会改写其配置，也不会搬迁历史会话。')
    for name in ('codex', 'pi', 'hermes'):
        found = discover(account, name)
        print(f'\n{name}：' + (f'发现 {found}' if found else '常见目录未发现，可手动填写路径'))
        if not yes(f'接入 {name}？'):
            continue
        executable = absolute_path('程序完整路径', found, account, executable=True)
        if name == 'codex':
            environment['PATH'] = str(Path(executable).parent) + ':' + BASE_PATH
            if Path(executable).name != 'codex':
                raise RuntimeError('Codex 接入要求程序名为 codex；请使用安装包提供的 codex 入口。')
            environment['CODEX_HOME'] = absolute_path('Codex 配置目录（复用其中的设置及凭据）',
                                                       str(Path(account.pw_dir) / '.codex'), account)
        elif name == 'pi':
            agents['pi'] = {'executable': executable, 'session_root': str(DATA / 'pi-sessions')}
            environment['PI_CODING_AGENT_DIR'] = absolute_path('Pi 配置目录',
                                                               str(Path(account.pw_dir) / '.pi/agent'), account)
        else:
            home = absolute_path('Hermes home（须对应正在使用的 Gateway）',
                                 str(Path(account.pw_dir) / '.hermes'), account)
            agents['hermes'] = {'executable': executable, 'home': home}
            environment['HERMES_HOME'] = home
            print('请确保该 home 的 Gateway 已运行；本脚本不会启动、停止或替换它。')
    needs_node = any(name in environment for name in ('CODEX_HOME', 'PI_CODING_AGENT_DIR'))
    if needs_node:
        print('\nnpm 安装的入口通常依赖 Node.js；独立原生二进制可以跳过。')
    if needs_node and yes('是否配置 Node.js 路径？', default=True):
        node = absolute_path('Node.js 程序完整路径', discover(account, 'node'), account, executable=True)
        if Path(node).name != 'node':
            raise RuntimeError('请使用名为 node 的 Node.js 程序入口。')
        environment['PATH'] = str(Path(node).parent) + ':' + environment.get('PATH', BASE_PATH)
    for name, label in (('claude', 'Claude Code'), ('deepseek', 'DeepSeek Harness')):
        print(f'\n{label} 使用 Runner 专用 Python SDK，不能仅复用其他环境的 CLI。')
        if yes(f'在 Runner 专用环境中安装 {label} 所需 SDK？'):
            sdk.append(name)
            if name == 'deepseek':
                agents[name] = {'dsh_home': str(DATA / 'deepseek')}
            else:
                environment['CLAUDE_CONFIG_DIR'] = str(DATA / 'claude-home')
            print('模型地址和 API key 稍后按指南配置，本脚本不会读取已有密钥。')
    return agents, environment, sdk


def create_file(path, content, mode=0o640, uid=0, gid=0):
    # O_EXCL also refuses existing symlinks, including dangling ones.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'w') as stream:
        os.fchmod(stream.fileno(), mode)
        os.fchown(stream.fileno(), uid, gid)
        stream.write(content)


def free_port(port):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError as error:
            raise RuntimeError(f'端口 {port} 已被占用，请确认现有服务；脚本不会停止它。') from error


def install_runner(account, agents, environment, sdk):
    previous = os.umask(0o022)
    try:
        _install_runner(account, agents, environment, sdk)
    finally:
        os.umask(previous)


def _install_runner(account, agents, environment, sdk):
    # Managed incomplete installs are intentionally NOT overwritten on retry.
    # Report partial state instead of guessing which files are safe to replace.
    for path, mode in ((CODE, 0o755), (CONFIG, 0o750), (DATA, 0o700)):
        path.mkdir(mode=mode)
        os.chown(path, 0 if path != DATA else account.pw_uid, account.pw_gid)
    shutil.copytree(SOURCE / 'agent_runner', CODE / 'agent_runner',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # copytree preserves source modes, including restrictive checkout permissions.
    for path in (CODE / 'agent_runner', *(CODE / 'agent_runner').rglob('*')):
        path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
    run([sys.executable, '-m', 'venv', CODE / 'venv'])
    run([CODE / 'venv/bin/python', '-m', 'pip', 'install', '-r', CODE / 'agent_runner/requirements.txt'])
    for name in sdk:
        run([CODE / 'venv/bin/python', '-m', 'pip', 'install', '-r',
             CODE / f'agent_runner/requirements-{name}.txt'])
    for name in ('pi-sessions', 'deepseek', 'claude-home'):
        path = DATA / name
        path.mkdir(mode=0o700)
        os.chown(path, account.pw_uid, account.pw_gid)
    config = {'host': '127.0.0.1', 'port': 51112, 'data_dir': str(DATA),
              'token_file': str(CONFIG / 'token'), 'max_concurrency': 3, 'workspaces': {}, 'agents': agents}
    create_file(CONFIG / 'config.json', json.dumps(config, ensure_ascii=False, indent=2) + '\n', gid=account.pw_gid)
    create_file(CONFIG / 'token', secrets.token_urlsafe(48) + '\n', 0o600, account.pw_uid, account.pw_gid)
    environment = {'PATH': BASE_PATH, **environment}
    create_file(CONFIG / 'environment', ''.join(f'{key}="{value}"\n' for key, value in environment.items()),
                gid=account.pw_gid)
    template = (SOURCE / 'deploy/chatraw-runner.service').read_text()
    create_file(UNIT, template.replace('@RUNNER_USER@', account.pw_name), 0o644)
    run(['runuser', '-u', account.pw_name, '--', CODE / 'venv/bin/python', '-c',
         'from agent_runner.registry import factories; factories()'], cwd=CODE)
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'enable', '--now', 'chatraw-runner'])
    run(['systemctl', 'is-active', '--quiet', 'chatraw-runner'])
    check_runner_health()


def runner_state():
    paths = (CODE, CONFIG, DATA, UNIT)
    present = [path for path in paths if os.path.lexists(path)]
    if not present:
        return 'new'
    required = (CODE / 'venv/bin/python', CONFIG / 'config.json', CONFIG / 'token', UNIT)
    if all(path.exists() for path in required):
        return 'existing'
    raise RuntimeError('发现已有或未完成的 Runner 安装：' + ', '.join(map(str, present)) +
                       '。已停止，未覆盖任何内容。请按 deploy/README.md 的“安装中断”说明处理。')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_json(url, token=None):
    # Never send local service credentials through a configured HTTP proxy or redirect.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token} if token else {})
    try:
        with opener.open(request, timeout=2) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        error.close()
        raise


def check_runner_health():
    token = (CONFIG / 'token').read_text().strip()
    for attempt in range(10):
        try:
            if local_json('http://127.0.0.1:51112/v1/health', token).get('service') == 'chatraw-agent-runner':
                print('Runner 身份及连接凭据检查：通过')
                return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise RuntimeError('Runner 未通过健康检查。请查看 sudo journalctl -u chatraw-runner -n 50 --no-pager。')


def inspect_existing_runner():
    config = json.loads((CONFIG / 'config.json').read_text())
    if config.get('host') != '127.0.0.1' or config.get('port') != 51112 or config.get('token_file') != str(CONFIG / 'token'):
        raise RuntimeError('现有 Runner 使用自定义地址或凭据路径。为保留配置，请按手动部署说明连接 ChatRaw。')
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'chatraw-runner']).returncode:
        raise RuntimeError('现有 Runner 未运行。本安装器不会重启或修复已有服务，请先查看 journalctl -u chatraw-runner。')
    check_runner_health()


def docker_state():
    containers = capture(['docker', 'container', 'ls', '-a', '--format', '{{.Names}}']).splitlines()
    if 'chatraw' in containers:
        return 'existing'
    volumes = capture(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines()
    if 'chatraw_chatraw_data' in volumes:
        raise RuntimeError('发现已有 chatraw_chatraw_data 数据卷，但没有 chatraw 容器。为避免将旧数据交给不匹配的代码，请按恢复说明操作。')
    free_port(51111)
    return 'new'


def compose():
    return ['docker', 'compose', '-p', 'chatraw', '-f', SOURCE / 'docker-compose.yml',
            '-f', SOURCE / 'deploy/docker-compose.agent.yml']


def summarize(container_state):
    print('\n安装操作完成，正在检查网页服务……')
    ready = False
    for attempt in range(10):
        try:
            result = local_json('http://127.0.0.1:51111/ready')
            ready = result.get('status') == 'ready'
            if ready:
                break
        except (OSError, ValueError):
            pass
        time.sleep(1)
    if not ready:
        raise RuntimeError('网页尚未就绪。请查看 docker logs --tail=50 chatraw，修正后重试。')
    print('ChatRaw 就绪检查：通过')
    if container_state == 'existing':
        print('已有 ChatRaw 容器未改动。请核对其 Runner 地址与 token 挂载；未配置时按手动部署说明接入。')
    print('访问地址：http://你的服务器IP:51111（本机可用 http://127.0.0.1:51111）')
    print('下一步：配置普通聊天模型；需要 Agent 时，在网页安装插件并检查可用性。')
    print('程序安装成功不代表模型链路已接通；模型地址、API key、Hermes Gateway 仍需按实际情况配置。')
    print('配置 /etc/chatraw-runner；Agent 数据 /var/lib/chatraw-runner；聊天数据在 Docker 卷中。')
    print(f'详细步骤：{SOURCE / "deploy/README.md"}')


def main():
    parser = argparse.ArgumentParser(description='ChatRaw 交互式安装；不覆盖已有配置或数据。')
    parser.add_argument('mode', choices=('new', 'existing'))
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('请在 Ubuntu/Linux 服务器上使用 sudo bash deploy/setup-new.sh 或 setup-existing.sh。')
    if not sys.stdin.isatty():
        raise RuntimeError('请在交互终端运行；本安装器需要你确认账户、路径和操作清单。')
    if sys.version_info < (3, 11):
        raise RuntimeError('Runner 需要 Python 3.11 或更新版本。')
    for command in ('docker', 'systemctl', 'runuser'):
        if not shutil.which(command):
            raise RuntimeError(f'缺少 {command}。请先按 deploy/README.md 准备 Docker Engine、Compose 和 systemd。')
    print('使用本机 Docker Engine：/var/run/docker.sock（不切换你的全局 Docker 上下文）')
    info = json.loads(capture(['docker', 'info', '--format', '{{json .}}']))
    if info.get('OSType') != 'linux' or 'docker desktop' in info.get('OperatingSystem', '').lower():
        raise RuntimeError('需要同一台 Linux 宿主机的 Docker Engine，不能使用 Docker Desktop 虚拟机或远程 Engine。')
    run(['docker', 'compose', 'version'])
    if not Path('/run/systemd/system').exists():
        raise RuntimeError('当前环境未运行 systemd，请在实际 Linux 主机上执行，而不是 Docker 容器内。')
    state = runner_state()
    container = docker_state()
    print('\nChatRaw 安装向导 — ' + ('新机器' if args.mode == 'new' else '接入已有 Agent'))
    print('不会安装全部 Agent，不会覆盖已有配置、数据或容器。Ctrl+C 可取消。')
    account = None
    agents, environment, sdk = {}, {}, []
    if state == 'existing':
        inspect_existing_runner()
        print('发现运行中的 Runner：保留现有配置、代码和服务，不安装 SDK、不重启。')
        print('如需为这个 Runner 添加 Agent，请按部署指南操作。')
    else:
        free_port(51112)
        default = os.environ.get('SUDO_USER', '')
        if default == 'root':
            default = ''
        while True:
            name = ask('用哪个已有普通账户运行 Runner', default)
            try:
                account = pwd.getpwnam(name)
                if account.pw_uid == 0:
                    raise ValueError()
                break
            except (KeyError, ValueError):
                print('请输入已有的非 root 账户，例如你平时运行 Agent 的账户。')
        # Check ensurepip before creating any installation files.
        try:
            run([sys.executable, '-c', 'import venv, ensurepip'], stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as error:
            raise RuntimeError('缺少 Python venv 支持。Ubuntu 请先执行 sudo apt-get install python3-venv，再重试。') from error
        if args.mode == 'existing':
            agents, environment, sdk = plan_agents(account)
    print('\n即将执行：')
    print(f'  Runner：{"复用，不修改" if state == "existing" else "新装并设置开机启动，账户 " + account.pw_name}')
    print(f'  ChatRaw：{"保留已有容器，不重建" if container == "existing" else "构建 Docker 镜像并新建容器和持久卷"}')
    print('  已选 Agent：' + (', '.join(sorted(set(agents) | set(sdk) | ({'codex'} if 'CODEX_HOME' in environment else set()))) or '无，稍后按需添加'))
    print('  新装路径：/opt/chatraw-runner、/etc/chatraw-runner、/var/lib/chatraw-runner')
    if environment:
        print('  使用的程序搜索路径和原生目录：')
        for key, value in environment.items():
            print(f'    {key}={value}')
    for name, settings in agents.items():
        print(f'    {name}: {json.dumps(settings, ensure_ascii=False)}')
    print('  下载：新装会下载 Python 依赖及 Docker 构建依赖；不调用付费模型 API。')
    if not yes('确认开始？'):
        print('已取消，未修改配置或数据。')
        return
    if state == 'new':
        if runner_state() != 'new':
            raise RuntimeError('确认期间出现了 Runner 安装；已停止，不修改新出现的环境。')
        install_runner(account, agents, environment, sdk)
    if container == 'new':
        if docker_state() != 'new':
            raise RuntimeError('安装期间出现了 chatraw 容器；已停止，不修改新出现的容器。')
        run(compose() + ['up', '-d', '--build', 'chatraw'],
            env={**os.environ, 'CHATRAW_RUNNER_TOKEN_FILE': str(CONFIG / 'token')})
    summarize(container)


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\n已中止。已完成的安装步骤会保留，不自动删除或回滚数据。', file=sys.stderr)
        sys.exit(130)
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'\n未完成：{error}', file=sys.stderr)
        print('未自动覆盖或删除旧配置。请修正错误后按部署文档继续；不要删除数据来强行重装。', file=sys.stderr)
        sys.exit(1)
