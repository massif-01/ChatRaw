"""Regression tests for PR review data handling and workflow isolation."""

import importlib.util
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
    def test_checked_snapshot_is_used_as_data_without_executing_it(self):
        files = [
            {"filename": "notes/readme.md", "patch": "ignored"},
            {"filename": "Plugins/demo/main.js", "patch": "+const x = 1;"},
            {
                "filename": "backend/new.py",
                "patch": "+__import__('os').system('unsafe')",
            },
            {"filename": "frontend/widget.mjs"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            snapshot = Path(temp) / "changes.json"
            snapshot.write_text(
                json.dumps({"base_sha": "base", "head_sha": "head", "files": files})
            )
            with patch.dict(
                os.environ,
                {
                    "PR_CHANGES_FILE": str(snapshot),
                    "PR_BASE_SHA": "base",
                    "PR_HEAD_SHA": "head",
                },
            ), patch.object(
                review.subprocess,
                "run",
                side_effect=AssertionError("PR data must not be executed"),
            ):
                reviewed_files, diff = review.get_code_diff()

        self.assertEqual(
            reviewed_files,
            ["Plugins/demo/main.js", "backend/new.py", "frontend/widget.mjs"],
        )
        self.assertIn("__import__('os').system('unsafe')", diff)
        self.assertIn("GitHub did not provide a textual patch", diff)

    def test_rejects_a_snapshot_from_another_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            snapshot = Path(temp) / "changes.json"
            snapshot.write_text(
                json.dumps({"base_sha": "base", "head_sha": "old", "files": []})
            )
            with patch.dict(os.environ, {"PR_BASE_SHA": "base", "PR_HEAD_SHA": "new"}):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    review.get_pr_patches(str(snapshot))

    def test_truncates_large_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            snapshot = Path(temp) / "changes.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "base_sha": "base",
                        "head_sha": "head",
                        "files": [
                            {"filename": "backend/main.py", "patch": "x" * 20000}
                        ],
                    }
                )
            )
            with patch.dict(os.environ, {"PR_BASE_SHA": "base", "PR_HEAD_SHA": "head"}):
                files, diff = review.get_pr_patches(str(snapshot))
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
        cls.comment = workflow.split("  comment:\n", 1)[1]
        script = cls.security.split("          script: |\n", 1)[1].split(
            "\n      - name: Fail", 1
        )[0]
        cls.classifier = textwrap.dedent(script).strip()
        cls.comment_script = textwrap.dedent(
            cls.comment.split("          script: |\n", 1)[1]
        ).strip()
        script = cls.auto.split("      - name: Static check", 1)[1].split(
            "        run: |\n", 1
        )[1]
        cls.static_check = textwrap.dedent(script).strip()

    def classify(self, files, changed_files, fail_api=False):
        runner = """
          const fs = require('fs');
          const input = JSON.parse(fs.readFileSync(0, 'utf8'));
          const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
          const context = { repo: {owner: 'a', repo: 'b'}, payload: {pull_request: {
            number: 1, changed_files: input.changed_files,
            base: {sha: 'a'.repeat(40)}, head: {sha: 'b'.repeat(40)}
          }}};
          let request;
          const github = {request: async (route, params) => {
            request = {route, params};
            if (input.fail_api) throw new Error('simulated API outage');
            return {data: {files: input.files}};
          }};
          const output = {}, warnings = [];
          const core = {setOutput: (key, value) => { output[key] = value; },
            notice: () => {}, warning: message => warnings.push(message)};
          new AsyncFunction('context', 'github', 'core', input.code)(context, github, core)
            .then(() => {
              const path = 'pr-review-data/changes.json';
              const snapshot = fs.existsSync(path) ? JSON.parse(fs.readFileSync(path)) : null;
              process.stdout.write(JSON.stringify({output, snapshot, request, warnings}));
            })
            .catch(error => { console.error(error); process.exitCode = 1; });
        """
        payload = json.dumps(
            {
                "code": self.classifier,
                "files": files,
                "changed_files": changed_files,
                "fail_api": fail_api,
            }
        )
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                ["node", "-e", runner],
                cwd=temp,
                input=payload,
                text=True,
                capture_output=True,
                check=True,
            )
        return json.loads(result.stdout)

    def report(self, mode="current", status="ok", result="success"):
        runner = """
          const fs = require('fs');
          const input = JSON.parse(fs.readFileSync(0, 'utf8'));
          const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
          const fn = new AsyncFunction('context', 'github', 'core', input.code);
          const old = 'b'.repeat(40), current = 'c'.repeat(40), base = 'a'.repeat(40);
          const state = {body: null, writes: [], notices: []};
          const issues = {
            listComments: () => {},
            createComment: async ({body}) => {state.body = body; state.writes.push(body);},
            updateComment: async ({body}) => {state.body = body; state.writes.push(body);}
          };
          const github = {
            rest: {issues, pulls: {get: async () => ({data: {
              head: {sha: current}, base: {sha: base}
            }})}},
            paginate: async () => state.body ? [{id: 1, user: {type: 'Bot'}, body: state.body}] : []
          };
          const core = {notice: message => state.notices.push(message)};
          const invoke = async head => {
            process.env.SECURITY_STATUS = input.status;
            process.env.SECURITY_RESULT = input.result;
            process.env.FILE_COUNT = '1';
            process.env.ADDITIONS = '2';
            process.env.DELETIONS = '1';
            const context = {repo: {owner: 'a', repo: 'b'}, payload: {pull_request: {
              number: 1, changed_files: 1, base: {sha: base}, head: {sha: head}
            }}};
            await fn(context, github, core);
          };
          (async () => {
            await invoke(current);
            if (input.mode === 'old-after-new') await invoke(old);
            process.stdout.write(JSON.stringify(state));
          })().catch(error => { console.error(error); process.exitCode = 1; });
        """
        payload = json.dumps(
            {
                "code": self.comment_script,
                "mode": mode,
                "status": status,
                "result": result,
            }
        )
        with tempfile.TemporaryDirectory() as temp:
            run = subprocess.run(
                ["node", "-e", runner],
                cwd=temp,
                input=payload,
                text=True,
                capture_output=True,
                check=True,
            )
        return json.loads(run.stdout)

    def test_metadata_policy_handles_plugins_renames_and_incomplete_lists(self):
        clean = self.classify(
            [{"filename": "Plugins/demo/main.js", "patch": "+const answer = 42;"}], 1
        )
        self.assertEqual(clean["output"]["safe_to_run"], "true")
        self.assertEqual(clean["output"]["has_reviewable_changes"], "true")
        self.assertEqual(clean["snapshot"]["base_sha"], "a" * 40)
        self.assertEqual(clean["snapshot"]["head_sha"], "b" * 40)
        self.assertEqual(
            clean["request"]["params"]["basehead"], "a" * 40 + "..." + "b" * 40
        )
        with tempfile.TemporaryDirectory() as temp:
            snapshot = Path(temp) / "changes.json"
            snapshot.write_text(json.dumps(clean["snapshot"]))
            with patch.dict(
                os.environ, {"PR_BASE_SHA": "a" * 40, "PR_HEAD_SHA": "b" * 40}
            ):
                files, diff = review.get_pr_patches(str(snapshot))
            self.assertEqual(files, ["Plugins/demo/main.js"])
            self.assertIn("+const answer = 42;", diff)
        sensitive = self.classify([{"filename": ".github/workflows/ci.yml"}], 1)
        self.assertEqual(sensitive["output"]["status"], "sensitive")
        self.assertIsNone(sensitive["snapshot"])
        renamed = self.classify(
            [
                {
                    "filename": "notes/old.txt",
                    "previous_filename": ".github/scripts/review.py",
                }
            ],
            1,
        )
        self.assertEqual(renamed["output"]["safe_to_run"], "false")
        incomplete = self.classify([{"filename": "Plugins/demo/main.js"}], 2)
        self.assertEqual(incomplete["output"]["status"], "incomplete")
        self.assertIsNone(incomplete["snapshot"])
        capped = self.classify(
            [{"filename": f"scripts/{n}.py"} for n in range(300)], 301
        )
        self.assertEqual(capped["output"]["status"], "incomplete")
        self.assertIsNone(capped["snapshot"])

    def test_api_failure_does_not_block_static_check_and_is_reported(self):
        failed = self.classify([], 1, fail_api=True)
        self.assertEqual(failed["output"]["status"], "api_error")
        self.assertIn("simulated API outage", failed["warnings"][0])
        self.assertIn("if: steps.check.outputs.status == 'api_error'", self.security)
        self.assertNotIn("needs:", self.auto)
        self.assertIn("github.event_name == 'pull_request'", self.auto)
        report = self.report(status="api_error", result="failure")
        self.assertIn("GitHub API 失败", report["body"])
        self.assertIn("变更统计不可用", report["body"])
        self.assertNotIn("修改了敏感文件", report["body"])

        sensitive = self.report(status="sensitive")
        self.assertIn("修改了敏感文件", sensitive["body"])
        self.assertNotIn("GitHub API 失败", sensitive["body"])
        incomplete = self.report(status="incomplete")
        self.assertIn("文件列表不完整", incomplete["body"])
        self.assertNotIn("GitHub API 失败", incomplete["body"])

    def test_old_run_finishing_after_new_run_cannot_overwrite_report(self):
        report = self.report(mode="old-after-new")
        self.assertEqual(len(report["writes"]), 1)
        self.assertIn("`" + "c" * 40 + "`", report["body"])
        self.assertNotIn("`" + "b" * 40 + "`", report["body"])
        self.assertEqual(len(report["notices"]), 1)
        self.assertIn(
            "group: pr-review-comment-${{ github.event.pull_request.number }}",
            self.comment,
        )
        self.assertIn("cancel-in-progress: false", self.comment)

    def test_privileged_jobs_do_not_checkout_pr_code(self):
        self.assertNotIn("actions/checkout", self.security)
        self.assertIn("github.event_name == 'pull_request'", self.auto)
        self.assertIn("persist-credentials: false", self.auto)
        self.assertIn("github.event_name == 'pull_request_target'", self.ai)
        self.assertIn("github.event.pull_request.base.sha", self.ai)
        self.assertNotIn("ref: ${{ github.event.pull_request.head.sha }}", self.ai)
        self.assertIn("PR_CHANGES_FILE: ../pr-review-data/changes.json", self.ai)
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
