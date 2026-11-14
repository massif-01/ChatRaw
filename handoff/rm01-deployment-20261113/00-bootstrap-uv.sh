#!/usr/bin/env bash
set -euo pipefail
sudo -n install -d -m 0755 -o rm01 -g rm01 /opt/chatraw-agents/tools/bin /opt/chatraw-agents/cache
python3 - <<'PY'
import hashlib,io,json,urllib.request,zipfile
from pathlib import Path
metadata=json.load(urllib.request.urlopen('https://pypi.org/pypi/uv/json'))
wheel=next(f for f in metadata['urls'] if f['filename'].endswith('manylinux_2_17_x86_64.manylinux2014_x86_64.whl'))
data=urllib.request.urlopen(wheel['url']).read()
assert hashlib.sha256(data).hexdigest()==wheel['digests']['sha256']
with zipfile.ZipFile(io.BytesIO(data)) as z:
 for binary in ('uv','uvx'):
  name=next(n for n in z.namelist() if n.endswith('/scripts/'+binary))
  path=Path('/opt/chatraw-agents/tools/bin')/binary
  path.write_bytes(z.read(name));path.chmod(0o755)
print(json.dumps({'tool':'uv','version':metadata['info']['version'],'wheel':wheel['filename'],'sha256':wheel['digests']['sha256']}))
PY
/opt/chatraw-agents/tools/bin/uv --version
