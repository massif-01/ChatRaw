#!/usr/bin/env bash
set -euo pipefail
sudo -n install -d -m 0755 -o rm01 -g rm01 /opt/chatraw-agents /opt/chatraw-agents/hermes /opt/chatraw-agents/cache /opt/chatraw-agents/python
if [[ ! -x /opt/chatraw-agents/tools/bin/uv ]]; then
  python3 -m venv /opt/chatraw-agents/tools
  /opt/chatraw-agents/tools/bin/python -m pip install uv
fi
pin=6a0d2d12815c0546b0bcaf05046e2fe3293f60aa
source_dir=/opt/chatraw-agents/hermes/source
if [[ ! -d "$source_dir/.git" ]]; then
  git init "$source_dir"
  git -C "$source_dir" remote add origin https://github.com/NousResearch/hermes-agent.git
  git -C "$source_dir" fetch --depth=1 origin "$pin"
  git -C "$source_dir" checkout --detach FETCH_HEAD
fi
test "$(git -C "$source_dir" rev-parse HEAD)" = "$pin"
export UV_CACHE_DIR=/opt/chatraw-agents/cache/uv
export UV_PYTHON_INSTALL_DIR=/opt/chatraw-agents/python
cd "$source_dir"
/opt/chatraw-agents/tools/bin/uv sync --locked --no-dev --python 3.14
/opt/chatraw-agents/tools/bin/uv pip install --python .venv/bin/python aiohttp==3.14.5
.venv/bin/python --version
.venv/bin/hermes --version
