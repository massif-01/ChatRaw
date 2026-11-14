"""Run legacy suites in separate processes to isolate module-global DATA_DIR.

Usage: /path/to/python -B docs/agent-platform/reviews/run_baseline.py
Only test doubles and loopback HTTP are used by these existing suites.
"""

import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[3]
MODULES = [
    "backend.test_context_compaction",
    "backend.test_fonts_route",
    "backend.test_hermes_bridge",
    "backend.test_hermes_smoke",
    "backend.test_http_session_tls",
    "backend.test_skills",
]


def main():
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    OUTPUT = Path(__file__).resolve().parent / f"baseline-{commit[:7]}"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["fastapi", "aiohttp", "pydantic", "certifi", "python-multipart"]
        },
        "boundary": "Legacy unit tests and local HTTP fake; no real agent/browser/RM01",
        "results": [],
    }
    for module in MODULES:
        command = [sys.executable, "-B", "-m", "unittest", module, "-v"]
        with tempfile.TemporaryDirectory(prefix="test-data-", dir=OUTPUT) as temporary:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=temporary)
            result = subprocess.run(
                command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=180
            )
        log = result.stdout + result.stderr
        log_name = module.rsplit(".", 1)[-1] + ".log"
        (OUTPUT / log_name).write_text(log, encoding="utf-8")
        count = re.search(r"Ran (\d+) tests? in", log)
        entry = {
            "module": module,
            "command": command,
            "returncode": result.returncode,
            "tests": int(count.group(1)) if count else None,
            "log": log_name,
        }
        report["results"].append(entry)
        print(json.dumps(entry), flush=True)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    (OUTPUT / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return int(any(row["returncode"] != 0 for row in report["results"]))


if __name__ == "__main__":
    raise SystemExit(main())
