"""Execute immutable snapshot suites, isolating backend module-global databases."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument("snapshot", type=Path)
parser.add_argument("evidence", type=Path)
args = parser.parse_args()
args.evidence.mkdir(parents=True, exist_ok=True)
commands = [("runner", ["discover", "-s", "agent_runner/tests", "-v"])]
commands += [(path.stem, [f"backend.{path.stem}", "-v"])
             for path in sorted((args.snapshot / "backend").glob("test_*.py"))]
results = []
for name, arguments in commands:
    command = [sys.executable, "-B", "-m", "unittest", *arguments]
    completed = subprocess.run(command, cwd=args.snapshot,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                               text=True, capture_output=True, timeout=180)
    log = completed.stdout + completed.stderr
    (args.evidence / f"{name}.log").write_text(log)
    match = re.search(r"Ran (\d+) tests? in", log)
    result = {"name": name, "command": command, "exit_code": completed.returncode,
              "tests": int(match[1]) if match else None,
              "skipped": len(re.findall(r"\.\.\. skipped", log))}
    results.append(result)
    print(json.dumps(result), flush=True)
(args.evidence / "regression-results.json").write_text(json.dumps(results, indent=2) + "\n")
raise SystemExit(any(row["exit_code"] != 0 for row in results))
