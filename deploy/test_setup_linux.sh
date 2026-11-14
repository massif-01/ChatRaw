#!/usr/bin/env bash
# CI-only smoke test on an ephemeral Ubuntu host. Never run on a deployment host.
set -euo pipefail
if [[ ${GITHUB_ACTIONS:-} != true || ${RUNNER_ENVIRONMENT:-} != github-hosted ]]; then
    echo 'This destructive isolation test only runs on GitHub-hosted CI.' >&2
    exit 2
fi
sudo apt-get update -qq
sudo apt-get install -y python3-venv
sudo useradd --create-home --shell /bin/bash chatrawtest
# script provides the same PTY as an SSH terminal; no model credentials are supplied.
printf 'chatrawtest\ny\n' | sudo script --return --quiet --command 'bash deploy/setup-new.sh' /dev/null
sudo systemctl is-active --quiet chatraw-runner
curl --fail --silent http://127.0.0.1:51111/ready
sudo sh -c 'find /etc/chatraw-runner -type f -exec sha256sum {} \; > /tmp/chatraw-setup-before.sha256'
sudo sh -c 'printf preserve > /var/lib/chatraw-runner/installer-test-sentinel'
started_before=$(sudo systemctl show chatraw-runner --property=ActiveEnterTimestampMonotonic --value)
container_before=$(docker inspect --format '{{.Id}}' chatraw)
printf 'y\n' | sudo script --return --quiet --command 'bash deploy/setup-existing.sh' /dev/null
sudo sha256sum --status --check /tmp/chatraw-setup-before.sha256
test "$(sudo cat /var/lib/chatraw-runner/installer-test-sentinel)" = preserve
test "$started_before" = "$(sudo systemctl show chatraw-runner --property=ActiveEnterTimestampMonotonic --value)"
test "$container_before" = "$(docker inspect --format '{{.Id}}' chatraw)"
echo 'Fresh install and existing deployment reuse passed; config, data, process and container preserved.'
