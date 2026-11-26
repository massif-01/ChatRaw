"""Regression tests for PR review data handling and workflow isolation."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pr-review.yml"
SPEC = importlib.util.spec_from_file_location(
    "chatraw_ai_review", ROOT / ".github/scripts/ai_review.py"
)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


class GithubPatchTest(unittest.TestCase):
    def test_pr_data_is_paginated_and_never_executed(self):
        first = [{"filename": f"notes/{i}.md", "patch": "ignored"} for i in range(99)]
        first.append({"filename": "Plugins/demo/main.js", "patch": "+const x = 1;"})
        second = [
            {
                "filename": "backend/new.py",
                "patch": "+__import__('os').system('unsafe')",
            },
            {"filename": "frontend/widget.mjs"},
        ]
        pages = [first, second]

        def fake_urlopen(request, timeout):
            self.assertEqual(timeout, 20)
            self.assertIn(
                "/repos/example/repo/pulls/12/files?per_page=100&page=",
                request.full_url,
            )
            self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
            return io.BytesIO(json.dumps(pages.pop(0)).encode())

        with patch.dict(
            os.environ,
            {
                "PR_NUMBER": "12",
                "GITHUB_REPOSITORY": "example/repo",
                "GITHUB_TOKEN": "test-token",
            },
        ), patch.object(
            review.urllib.request, "urlopen", side_effect=fake_urlopen
        ), patch.object(
            review.subprocess,
            "run",
            side_effect=AssertionError("PR data must not be executed"),
        ):
            files, diff = review.get_code_diff()

        self.assertEqual(
            files, ["Plugins/demo/main.js", "backend/new.py", "frontend/widget.mjs"]
        )
        self.assertIn("__import__('os').system('unsafe')", diff)
        self.assertIn("GitHub did not provide a textual patch", diff)
        self.assertEqual(pages, [])

    def test_rejects_invalid_repository_or_pr_number_before_request(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "example/repo/../other",
                "GITHUB_TOKEN": "test-token",
            },
        ), patch.object(review.urllib.request, "urlopen") as request:
            with self.assertRaises(ValueError):
                review.get_pr_patches("12")
            request.assert_not_called()
        with patch.dict(
            os.environ,
            {"GITHUB_REPOSITORY": "example/repo", "GITHUB_TOKEN": "test-token"},
        ), patch.object(review.urllib.request, "urlopen") as request:
            with self.assertRaises(ValueError):
                review.get_pr_patches("1/../2")
            request.assert_not_called()

    def test_truncates_large_patch(self):
        payload = [{"filename": "backend/main.py", "patch": "x" * 20000}]
        with patch.dict(
            os.environ,
            {"GITHUB_REPOSITORY": "example/repo", "GITHUB_TOKEN": "test-token"},
        ), patch.object(
            review.urllib.request,
            "urlopen",
            return_value=io.BytesIO(json.dumps(payload).encode()),
        ):
            files, diff = review.get_pr_patches("12")
        self.assertEqual(files, ["backend/main.py"])
        self.assertIn("diff 已截断", diff)
        self.assertLess(len(diff), 16000)


class WorkflowPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = WORKFLOW.read_text()
        cls.security = workflow.split("  security-check:\n", 1)[1].split(
            "  auto-check:\n", 1
        )[0]
        cls.auto = workflow.split("  auto-check:\n", 1)[1].split("  ai-review:\n", 1)[0]
        cls.ai = workflow.split("  ai-review:\n", 1)[1].split("  labeler:\n", 1)[0]
        script = cls.security.split("          script: |\n", 1)[1]
        cls.classifier = textwrap.dedent(script).strip()
        script = cls.auto.split("      - name: Static check", 1)[1].split(
            "        run: |\n", 1
        )[1]
        cls.static_check = textwrap.dedent(script).strip()

    def classify(self, files, changed_files):
        runner = """
          const fs = require('fs');
          const input = JSON.parse(fs.readFileSync(0, 'utf8'));
          const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
          const context = { repo: {owner: 'a', repo: 'b'}, payload: {pull_request: {
            number: 1, changed_files: input.changed_files
          }}};
          const github = {rest: {pulls: {listFiles: () => {}}}, paginate: async () => input.files};
          const output = {};
          const core = {setOutput: (key, value) => { output[key] = value; }, notice: () => {}};
          new AsyncFunction('context', 'github', 'core', input.code)(context, github, core)
            .then(() => process.stdout.write(JSON.stringify(output)))
            .catch(error => { console.error(error); process.exitCode = 1; });
        """
        payload = json.dumps(
            {"code": self.classifier, "files": files, "changed_files": changed_files}
        )
        result = subprocess.run(
            ["node", "-e", runner],
            input=payload,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_metadata_policy_handles_plugins_renames_and_incomplete_lists(self):
        clean = self.classify([{"filename": "Plugins/demo/main.js"}], 1)
        self.assertEqual(
            clean, {"safe_to_run": "true", "has_reviewable_changes": "true"}
        )
        sensitive = self.classify([{"filename": ".github/workflows/ci.yml"}], 1)
        self.assertEqual(sensitive["safe_to_run"], "false")
        renamed = self.classify(
            [
                {
                    "filename": "notes/old.txt",
                    "previous_filename": ".github/scripts/review.py",
                }
            ],
            1,
        )
        self.assertEqual(renamed["safe_to_run"], "false")
        incomplete = self.classify([{"filename": "Plugins/demo/main.js"}], 2)
        self.assertEqual(incomplete["safe_to_run"], "false")

    def test_privileged_jobs_do_not_checkout_pr_code(self):
        self.assertNotIn("actions/checkout", self.security)
        self.assertIn("github.event_name == 'pull_request'", self.auto)
        self.assertIn("persist-credentials: false", self.auto)
        self.assertIn("github.event_name == 'pull_request_target'", self.ai)
        self.assertIn("github.event.pull_request.base.sha", self.ai)
        self.assertNotIn("github.event.pull_request.head", self.ai)
        self.assertIn("python -I .github/scripts/ai_review.py", self.ai)

    def test_static_check_handles_paths_and_reports_syntax_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "python").symlink_to(sys.executable)
            flake8 = bin_dir / "flake8"
            flake8.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$FLAKE8_ARGS"\n')
            flake8.chmod(0o755)

            def git(*args):
                return subprocess.run(
                    ["git", *args], cwd=repo, capture_output=True, text=True, check=True
                ).stdout.strip()

            def commit(message):
                git("add", "-A")
                git(
                    "-c",
                    "user.name=CI",
                    "-c",
                    "user.email=ci@example.invalid",
                    "commit",
                    "-qm",
                    message,
                )

            git("init", "-q")
            (repo / "removed.py").write_text("old = True\n")
            commit("base")
            base_sha = git("rev-parse", "HEAD")
            (repo / "removed.py").unlink()
            spaced = repo / "folder with spaces"
            spaced.mkdir()
            (spaced / "valid.py").write_text("answer = 42\n")
            commit("valid")

            env = os.environ | {
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "PR_BASE_SHA": base_sha,
                "GITHUB_OUTPUT": str(root / "output"),
                "GITHUB_STEP_SUMMARY": str(root / "summary"),
                "FLAKE8_ARGS": str(root / "flake8-args"),
            }
            result = subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", self.static_check],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("syntax_ok=true", (root / "output").read_text())
            self.assertIn("1 个 Python 文件", (root / "summary").read_text())
            self.assertIn(
                "folder with spaces/valid.py", (root / "flake8-args").read_text()
            )

            (spaced / "bad.py").write_text("def broken(:\n")
            commit("invalid")
            result = subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", self.static_check],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("syntax_ok=false", (root / "output").read_text())


if __name__ == "__main__":
    unittest.main()
