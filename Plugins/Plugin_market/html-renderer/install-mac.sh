#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
    printf '%s\n' 'This helper is for macOS.' >&2
    exit 1
fi

plugin_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
agent_label='com.chatraw.html-renderer'
agent_file="$HOME/Library/LaunchAgents/$agent_label.plist"
agent_domain="gui/$(id -u)"

if [ "${1:-}" = "--remove" ]; then
    /bin/launchctl bootout "$agent_domain/$agent_label" 2>/dev/null || true
    rm -f "$agent_file"
    printf '%s\n' 'Browser helper removed.'
    exit 0
fi

python_bin=$(command -v python3 || true)
if [ -z "$python_bin" ]; then
    printf '%s\n' 'Python 3 is required to run the included browser helper.' >&2
    exit 1
fi

mkdir -p "$(dirname -- "$agent_file")"
/bin/launchctl bootout "$agent_domain/$agent_label" 2>/dev/null || true
umask 077
"$python_bin" - "$agent_file" "$agent_label" "$python_bin" "$plugin_dir/bridge.py" <<'PY'
import plistlib
import sys

agent_file, label, python_bin, bridge = sys.argv[1:]
config = {
    "Label": label,
    "ProgramArguments": [python_bin, bridge],
    "RunAtLoad": True,
}
with open(agent_file, "wb") as handle:
    plistlib.dump(config, handle)
PY

/bin/launchctl bootstrap "$agent_domain" "$agent_file"
for attempt in 1 2 3 4 5; do
    agent_pid=$(/bin/launchctl print "$agent_domain/$agent_label" 2>/dev/null | /usr/bin/awk '/pid = / { print $3; exit }')
    health=$(/usr/bin/curl --silent --fail --max-time 1 http://127.0.0.1:38479/health || true)
    if [ -n "$agent_pid" ] && printf '%s' "$health" | /usr/bin/grep -Fq "\"service\":\"chatraw-html-renderer\",\"pid\":$agent_pid}"; then
        printf '%s\n' 'Browser helper enabled.'
        exit 0
    fi
    sleep 1
done
/bin/launchctl bootout "$agent_domain/$agent_label" 2>/dev/null || true
rm -f "$agent_file"
printf '%s\n' 'The browser helper did not start; check whether port 38479 is already in use.' >&2
exit 1
