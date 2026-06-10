import asyncio
import io
import os
import json
import shutil
import sys
import tempfile
import unittest
import zipfile

TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-skills-test-")
os.environ["DATA_DIR"] = TEST_DATA_DIR

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend import main  # noqa: E402
from starlette.routing import Match  # noqa: E402


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class JsonRequest:
    def __init__(self, body):
        self.body = body

    async def json(self):
        return self.body


class FakeChatContent:
    async def iter_any(self):
        yield b'data: {"choices":[{"delta":{"content":"stream reply"}}]}\n'
        yield b"data: [DONE]\n"


class FakeChatResponse:
    def __init__(self, stream=False):
        self.status = 200
        self.stream = stream
        self.content = FakeChatContent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return {"choices": [{"message": {"content": "assistant reply"}}]}

    async def text(self):
        return ""


class FakeChatSession:
    def __init__(self):
        self.posts = []

    def post(self, url, json=None, headers=None):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return FakeChatResponse(stream=bool(json and json.get("stream")))


class SkillRegistryTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(main.SKILLS_DIR, ignore_errors=True)
        os.makedirs(main.SKILLS_INSTALLED_DIR, exist_ok=True)
        shutil.rmtree(main.PLUGINS_DIR, ignore_errors=True)
        os.makedirs(main.PLUGINS_INSTALLED_DIR, exist_ok=True)
        os.makedirs(main.PLUGINS_DIR, exist_ok=True)
        main.save_plugin_config({"plugins": {}, "api_keys": {}})

        conn = main.db.get_conn()
        cursor = conn.cursor()
        for table in (
            "chat_skill_activations",
            "chat_compactions",
            "messages",
            "chats",
        ):
            cursor.execute(f"DELETE FROM {table}")
        conn.commit()
        main._context_compaction_locks.clear()

    def write_config(self, skills):
        main.save_skill_config({"schema_version": 1, "skills": skills})

    def write_skill(self, skill_name, content, resources=None):
        skill_dir = os.path.join(main.SKILLS_INSTALLED_DIR, skill_name)
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(content)
        for rel_path, rel_content in (resources or {}).items():
            full_path = os.path.join(skill_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(rel_content)
        return skill_dir

    def skill_entry(self, skill_name, enabled=True, diagnostics=None, trusted=False):
        return {
            "name": skill_name,
            "description": f"{skill_name} description",
            "license": "MIT",
            "compatibility": "ChatRaw",
            "metadata": {
                "display_name": skill_name.title(),
                "alias": f"{skill_name}-alias",
            },
            "enabled": enabled,
            "trusted": trusted,
            "source": {"type": "local"},
            "installed_at": "2026-06-10T00:00:00",
            "updated_at": "2026-06-10T00:00:00",
            "diagnostics": diagnostics or [],
        }

    def api_result(self, result):
        if isinstance(result, main.JSONResponse):
            return result.status_code, json.loads(result.body.decode("utf-8"))
        return 200, result

    def first_route_match(self, path, method="GET"):
        scope = {"type": "http", "path": path, "method": method}
        for route in main.app.routes:
            match, _ = route.matches(scope)
            if match == Match.FULL:
                return route
        return None

    def upload_file(self, filename, content):
        return main.UploadFile(file=io.BytesIO(content), filename=filename)

    def zip_bytes(self, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            for path, content in files.items():
                zf.writestr(path, content)
        return buffer.getvalue()

    def zip_with_symlink(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            info = zipfile.ZipInfo("SKILL.md")
            info.external_attr = 0o120777 << 16
            zf.writestr(info, "target")
        return buffer.getvalue()

    def install_upload(self, filename, content, overwrite=False, enabled=True):
        return self.api_result(
            asyncio.run(
                main.upload_skill(
                    file=self.upload_file(filename, content),
                    overwrite=overwrite,
                    enabled=enabled,
                )
            )
        )

    def patch_github(self, contents, downloads):
        original_contents = main.fetch_github_contents
        original_bytes = main.fetch_url_bytes
        original_session = main.get_http_session

        async def fake_session():
            return object()

        async def fake_contents(session, owner, repo, path, ref):
            return contents.get((owner, repo, path, ref))

        async def fake_bytes(session, url, max_size):
            data = downloads[url]
            if len(data) > max_size:
                raise main.SkillInstallError("Skill package exceeds maximum size")
            return data

        main.get_http_session = fake_session
        main.fetch_github_contents = fake_contents
        main.fetch_url_bytes = fake_bytes
        self.addCleanup(lambda: setattr(main, "get_http_session", original_session))
        self.addCleanup(
            lambda: setattr(main, "fetch_github_contents", original_contents)
        )
        self.addCleanup(lambda: setattr(main, "fetch_url_bytes", original_bytes))

    def enable_skill_manager(self, enabled=True):
        plugin_dir = os.path.join(
            main.PLUGINS_INSTALLED_DIR, main.SKILL_MANAGER_PLUGIN_ID
        )
        os.makedirs(plugin_dir, exist_ok=True)
        with open(
            os.path.join(plugin_dir, "manifest.json"), "w", encoding="utf-8"
        ) as f:
            json.dump({"id": main.SKILL_MANAGER_PLUGIN_ID}, f)
        main.save_plugin_config(
            {
                "plugins": {
                    main.SKILL_MANAGER_PLUGIN_ID: {
                        "enabled": enabled,
                        "settings_values": {},
                    }
                },
                "api_keys": {},
            }
        )

    def enable_context_compressor(self, auto_compress=False):
        plugin_dir = os.path.join(
            main.PLUGINS_INSTALLED_DIR, main.CONTEXT_COMPRESSOR_PLUGIN_ID
        )
        os.makedirs(plugin_dir, exist_ok=True)
        config = main.load_plugin_config()
        config.setdefault("plugins", {})
        config["plugins"][main.CONTEXT_COMPRESSOR_PLUGIN_ID] = {
            "enabled": True,
            "settings_values": {"autoCompress": auto_compress},
        }
        main.save_plugin_config(config)

    def configure_chat(
        self, stream=False, vision=True, system_prompt="Base system prompt."
    ):
        settings = main.db.get_settings()
        settings.chat_settings.stream = stream
        settings.chat_settings.system_prompt = system_prompt
        main.db.save_settings(settings)
        main.db.save_model_config(
            main.ModelConfig(
                id="default-chat",
                name="Test Chat",
                api_url="https://chat.test/v1",
                model_id="fake-chat",
                context_length=8192,
                max_output=1024,
                type="chat",
                capability=main.ModelCapability(vision=vision),
            )
        )

    def patch_chat_session(self):
        original_session = main.get_http_session
        fake_session = FakeChatSession()

        async def fake_get_http_session():
            return fake_session

        main.get_http_session = fake_get_http_session
        self.addCleanup(lambda: setattr(main, "get_http_session", original_session))
        return fake_session

    def write_registered_skill(
        self,
        skill_name,
        content=None,
        enabled=True,
        resources=None,
        source=None,
        diagnostics=None,
        trusted=False,
    ):
        if content is None:
            content = f"---\nname: {skill_name}\ndescription: {skill_name} desc\n---\nSECRET-SKILL-BODY {skill_name}"
        entry = self.skill_entry(
            skill_name, enabled=enabled, diagnostics=diagnostics, trusted=trusted
        )
        if source is not None:
            entry["source"] = source
        self.write_config({skill_name: entry})
        self.write_skill(skill_name, content, resources=resources)
        return entry

    def chat(self, body):
        return self.api_result(asyncio.run(main.chat(JsonRequest(body))))

    def activation_rows(self, chat_id=None):
        cursor = main.db.get_conn().cursor()
        if chat_id:
            cursor.execute(
                "SELECT * FROM chat_skill_activations WHERE chat_id = ? ORDER BY created_at ASC",
                (chat_id,),
            )
        else:
            cursor.execute(
                "SELECT * FROM chat_skill_activations ORDER BY created_at ASC"
            )
        return [dict(row) for row in cursor.fetchall()]

    def test_validate_skill_name_accepts_safe_names(self):
        for skill_name in ("pdf-processing", "skill1"):
            with self.subTest(skill_name=skill_name):
                self.assertTrue(main.validate_skill_name(skill_name))

    def test_validate_skill_name_rejects_invalid_names(self):
        for skill_name in (
            "PDF",
            "-pdf",
            "pdf-",
            "pdf--x",
            "../pdf",
            "pdf/x",
            r"pdf\x",
            "",
        ):
            with self.subTest(skill_name=skill_name):
                self.assertFalse(main.validate_skill_name(skill_name))
                with self.assertRaises(main.HTTPException):
                    main.resolve_skill_dir(skill_name)

    def test_parse_skill_markdown_extracts_frontmatter_body_and_metadata(self):
        parsed = main.parse_skill_markdown(
            """---
name: pdf-processing
description: Extract PDF tables when the user mentions PDFs.
license: MIT
compatibility: ChatRaw
metadata:
  display_name: PDF Processing
  alias: pdf
---

Use this skill for PDF work.
""",
            expected_name="pdf-processing",
        )

        self.assertEqual(parsed["frontmatter"]["name"], "pdf-processing")
        self.assertEqual(
            parsed["frontmatter"]["metadata"]["display_name"], "PDF Processing"
        )
        self.assertEqual(parsed["body"], "Use this skill for PDF work.")
        self.assertEqual(parsed["diagnostics"], [])

    def test_parse_skill_markdown_reports_format_errors(self):
        cases = [
            ("no frontmatter", "Missing YAML frontmatter"),
            (
                "---\nname: missing-description\n---",
                "Missing required field: description",
            ),
            ("---\ndescription: Missing name\n---", "Missing required field: name"),
            ("---\nname: BadName\ndescription: Bad name\n---", "Invalid skill name"),
            (
                "---\nname: one\ndescription: Wrong dir\n---",
                "Skill name does not match directory name",
            ),
            (
                "---\nname: complex\ndescription: Complex metadata\nmetadata:\n  aliases:\n    - pdf\n---",
                "Unsupported metadata value",
            ),
        ]

        for content, expected in cases:
            with self.subTest(expected=expected):
                parsed = main.parse_skill_markdown(content, expected_name="expected")
                self.assertTrue(any(expected in item for item in parsed["diagnostics"]))

    def test_list_skills_returns_only_enabled_metadata_by_default(self):
        self.write_config(
            {
                "enabled-skill": self.skill_entry("enabled-skill", enabled=True),
                "disabled-skill": self.skill_entry("disabled-skill", enabled=False),
            }
        )

        status, data = self.api_result(asyncio.run(main.get_skills()))
        self.assertEqual(status, 200)

        self.assertEqual([skill["name"] for skill in data["skills"]], ["enabled-skill"])
        self.assertNotIn("body", data["skills"][0])

    def test_list_skills_uses_config_key_as_canonical_name(self):
        entry = self.skill_entry("pdf-processing", enabled=True)
        entry["name"] = "PDF"
        self.write_config({"pdf-processing": entry})

        status, data = self.api_result(asyncio.run(main.get_skills()))

        self.assertEqual(status, 200)
        self.assertEqual(data["skills"][0]["name"], "pdf-processing")

    def test_list_skills_include_disabled_returns_disabled_metadata(self):
        self.write_config(
            {
                "enabled-skill": self.skill_entry("enabled-skill", enabled=True),
                "disabled-skill": self.skill_entry("disabled-skill", enabled=False),
            }
        )

        status, data = self.api_result(
            asyncio.run(main.get_skills(include_disabled=True))
        )
        self.assertEqual(status, 200)
        names = [skill["name"] for skill in data["skills"]]

        self.assertEqual(names, ["disabled-skill", "enabled-skill"])

    def test_unregistered_installed_directory_is_not_listed(self):
        self.write_config({})
        self.write_skill(
            "orphan-skill",
            "---\nname: orphan-skill\ndescription: Orphan skill\n---\nOrphan body",
        )

        status, data = self.api_result(
            asyncio.run(main.get_skills(include_disabled=True))
        )
        self.assertEqual(status, 200)

        self.assertEqual(data["skills"], [])

    def test_detail_returns_metadata_and_resource_summary_without_body(self):
        self.write_config(
            {"pdf-processing": self.skill_entry("pdf-processing", enabled=True)}
        )
        self.write_skill(
            "pdf-processing",
            "---\nname: pdf-processing\ndescription: PDF work\n---\nBody",
            resources={
                "scripts/run.py": "print('ok')",
                "references/ref.md": "Reference",
                "assets/template.txt": "Template",
                "README.md": "Not a listed resource",
            },
        )

        status, data = self.api_result(
            asyncio.run(main.get_skill_detail("pdf-processing"))
        )
        self.assertEqual(status, 200)

        self.assertEqual(data["name"], "pdf-processing")
        self.assertEqual(data["resources"]["count"], 3)
        self.assertNotIn("body", data)

    def test_content_returns_raw_text_and_body_as_json(self):
        self.write_config(
            {"pdf-processing": self.skill_entry("pdf-processing", enabled=True)}
        )
        self.write_skill(
            "pdf-processing",
            "---\nname: pdf-processing\ndescription: PDF work\n---\n<b>raw text</b>",
        )

        status, data = self.api_result(
            asyncio.run(main.get_skill_content("pdf-processing"))
        )
        self.assertEqual(status, 200)

        self.assertEqual(data["body"], "<b>raw text</b>")
        self.assertIn("<b>raw text</b>", data["raw_text"])
        self.assertNotIn("html", data)

    def test_content_rejects_oversized_skill_file(self):
        self.write_config(
            {"large-skill": self.skill_entry("large-skill", enabled=True)}
        )
        self.write_skill("large-skill", "x" * (main.MAX_SKILL_FILE_SIZE + 1))

        status, data = self.api_result(
            asyncio.run(main.get_skill_content("large-skill"))
        )

        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "SKILL.md exceeds maximum size")

    def test_resources_returns_only_allowed_resource_directories(self):
        self.write_config(
            {"pdf-processing": self.skill_entry("pdf-processing", enabled=True)}
        )
        self.write_skill(
            "pdf-processing",
            "---\nname: pdf-processing\ndescription: PDF work\n---\nBody",
            resources={
                "scripts/run.py": "print('ok')",
                "references/ref.md": "Reference",
                "assets/template.txt": "Template",
                "other/ignore.txt": "Ignored",
                "README.md": "Ignored",
            },
        )

        status, data = self.api_result(
            asyncio.run(main.get_skill_resources("pdf-processing"))
        )
        self.assertEqual(status, 200)
        paths = [item["path"] for item in data["resources"]]

        self.assertEqual(
            paths, ["scripts/run.py", "references/ref.md", "assets/template.txt"]
        )

    def test_resources_skip_allowed_directory_symlink_to_outside(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink is not available")

        self.write_config(
            {"linked-skill": self.skill_entry("linked-skill", enabled=True)}
        )
        skill_dir = self.write_skill(
            "linked-skill",
            "---\nname: linked-skill\ndescription: Linked skill\n---\nBody",
        )
        outside_dir = tempfile.mkdtemp(prefix="chatraw-skill-outside-")
        self.addCleanup(lambda: shutil.rmtree(outside_dir, ignore_errors=True))
        with open(os.path.join(outside_dir, "secret.txt"), "w", encoding="utf-8") as f:
            f.write("secret")
        os.symlink(outside_dir, os.path.join(skill_dir, "references"))

        status, data = self.api_result(
            asyncio.run(main.get_skill_resources("linked-skill"))
        )

        self.assertEqual(status, 200)
        self.assertEqual(data["resources"], [])

    def test_resources_skip_allowed_directory_symlink_to_skill_root(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink is not available")

        self.write_config(
            {"linked-skill": self.skill_entry("linked-skill", enabled=True)}
        )
        skill_dir = self.write_skill(
            "linked-skill",
            "---\nname: linked-skill\ndescription: Linked skill\n---\nBody",
            resources={"README.md": "Not a resource"},
        )
        os.symlink(skill_dir, os.path.join(skill_dir, "assets"))

        status, data = self.api_result(
            asyncio.run(main.get_skill_resources("linked-skill"))
        )

        self.assertEqual(status, 200)
        self.assertEqual(data["resources"], [])

    def test_resources_limit_is_enforced(self):
        self.write_config({"many-files": self.skill_entry("many-files", enabled=True)})
        resources = {
            f"references/file-{idx:03}.md": str(idx)
            for idx in range(main.MAX_SKILL_RESOURCE_FILES + 5)
        }
        self.write_skill(
            "many-files",
            "---\nname: many-files\ndescription: Many files\n---\nBody",
            resources=resources,
        )

        status, data = self.api_result(
            asyncio.run(main.get_skill_resources("many-files"))
        )
        self.assertEqual(status, 200)

        self.assertEqual(data["count"], main.MAX_SKILL_RESOURCE_FILES)
        self.assertTrue(data["truncated"])

    def test_skill_api_errors_for_invalid_or_missing_skill(self):
        self.write_config({})

        invalid_status, _ = self.api_result(asyncio.run(main.get_skill_detail("PDF")))
        missing_status, _ = self.api_result(
            asyncio.run(main.get_skill_detail("pdf-processing"))
        )
        missing_content_status, _ = self.api_result(
            asyncio.run(main.get_skill_content("pdf-processing"))
        )
        missing_resources_status, _ = self.api_result(
            asyncio.run(main.get_skill_resources("pdf-processing"))
        )

        self.assertEqual(invalid_status, 400)
        self.assertEqual(missing_status, 404)
        self.assertEqual(missing_content_status, 404)
        self.assertEqual(missing_resources_status, 404)

    def test_upload_markdown_installs_skill_using_frontmatter_name(self):
        status, data = self.install_upload(
            "not-the-name.md",
            b"---\nname: uploaded-skill\ndescription: Uploaded skill\n---\nUse it.",
        )

        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["skill"]["name"], "uploaded-skill")
        self.assertTrue(data["skill"]["enabled"])
        self.assertFalse(data["skill"]["trusted"])
        self.assertNotIn("body", data["skill"])
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    main.SKILLS_INSTALLED_DIR,
                    "uploaded-skill",
                    "SKILL.md",
                )
            )
        )

    def test_upload_markdown_rejects_missing_description(self):
        status, data = self.install_upload(
            "skill.md", b"---\nname: no-description\n---\nBody"
        )

        self.assertEqual(status, 400)
        self.assertFalse(data["success"])

    def test_upload_markdown_rejects_non_utf8_skill_file(self):
        status, data = self.install_upload("skill.md", b"\xff\xfe\xfd")

        self.assertEqual(status, 400)
        self.assertIn("UTF-8", data["error"])

    def test_upload_markdown_duplicate_requires_overwrite(self):
        first_status, _ = self.install_upload(
            "skill.md",
            b"---\nname: duplicate-skill\ndescription: First\n---\nBody",
        )
        second_status, data = self.install_upload(
            "skill.md",
            b"---\nname: duplicate-skill\ndescription: Second\n---\nBody",
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 409)
        self.assertEqual(data["error"], "Skill already installed")

    def test_upload_overwrite_preserves_installed_at_and_refreshes_updated_at(self):
        original_timestamp = main._skill_timestamp
        timestamps = iter(["2026-06-10T00:00:00Z", "2026-06-10T00:00:01Z"])
        main._skill_timestamp = lambda: next(timestamps)
        self.addCleanup(lambda: setattr(main, "_skill_timestamp", original_timestamp))

        first_status, first_data = self.install_upload(
            "skill.md",
            b"---\nname: overwrite-skill\ndescription: First\n---\nFirst body",
        )
        second_status, second_data = self.install_upload(
            "skill.md",
            b"---\nname: overwrite-skill\ndescription: Second\n---\nSecond body",
            overwrite=True,
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(
            first_data["skill"]["installed_at"],
            second_data["skill"]["installed_at"],
        )
        self.assertNotEqual(
            first_data["skill"]["updated_at"],
            second_data["skill"]["updated_at"],
        )
        with open(
            os.path.join(main.SKILLS_INSTALLED_DIR, "overwrite-skill", "SKILL.md"),
            encoding="utf-8",
        ) as f:
            raw_text = f.read()
        self.assertIn("Second body", raw_text)

    def test_upload_overwrite_restores_old_directory_when_config_save_fails(self):
        first_status, _ = self.install_upload(
            "skill.md",
            b"---\nname: rollback-skill\ndescription: First\n---\nFirst body",
        )
        self.assertEqual(first_status, 200)

        original_save = main.save_skill_config
        original_logger_error = main.logger.error

        def failing_save(config):
            raise RuntimeError("save failed")

        main.save_skill_config = failing_save
        main.logger.error = lambda *args, **kwargs: None
        self.addCleanup(lambda: setattr(main, "save_skill_config", original_save))
        self.addCleanup(lambda: setattr(main.logger, "error", original_logger_error))

        second_status, data = self.install_upload(
            "skill.md",
            b"---\nname: rollback-skill\ndescription: Second\n---\nSecond body",
            overwrite=True,
        )

        self.assertEqual(second_status, 500)
        self.assertEqual(data["error"], "save failed")
        with open(
            os.path.join(main.SKILLS_INSTALLED_DIR, "rollback-skill", "SKILL.md"),
            encoding="utf-8",
        ) as f:
            raw_text = f.read()
        self.assertIn("First body", raw_text)

        main.save_skill_config = original_save
        main.logger.error = original_logger_error
        self.assertEqual(
            main.load_skill_config()["skills"]["rollback-skill"]["description"],
            "First",
        )

    def test_zip_upload_accepts_root_and_single_wrapper_directory(self):
        root_status, root_data = self.install_upload(
            "root.zip",
            self.zip_bytes(
                {
                    "SKILL.md": "---\nname: zip-root\ndescription: Zip root\n---\nBody",
                    "scripts/run.py": "print('ok')",
                }
            ),
        )
        wrapper_status, wrapper_data = self.install_upload(
            "wrapper.zip",
            self.zip_bytes(
                {
                    "packed/SKILL.md": "---\nname: zip-wrapper\ndescription: Zip wrapper\n---\nBody",
                    "packed/assets/example.txt": "asset",
                }
            ),
        )

        self.assertEqual(root_status, 200)
        self.assertEqual(root_data["skill"]["resources"]["count"], 1)
        self.assertEqual(wrapper_status, 200)
        self.assertEqual(wrapper_data["skill"]["name"], "zip-wrapper")

    def test_zip_upload_rejects_unsafe_or_missing_skill_packages(self):
        cases = [
            {"references/ref.md": "missing skill"},
            {
                "SKILL.md": "---\nname: multi-skill\ndescription: Multi\n---\nBody",
                "nested/SKILL.md": "---\nname: other\ndescription: Other\n---\nBody",
            },
            {"../SKILL.md": "---\nname: traversal\ndescription: Bad\n---\nBody"},
            {r"bad\SKILL.md": "---\nname: backslash\ndescription: Bad\n---\nBody"},
            {"/SKILL.md": "---\nname: absolute\ndescription: Bad\n---\nBody"},
            {"C:/SKILL.md": "---\nname: drive-path\ndescription: Bad\n---\nBody"},
        ]

        for files in cases:
            with self.subTest(files=list(files.keys())):
                status, data = self.install_upload("bad.zip", self.zip_bytes(files))
                self.assertEqual(status, 400)
                self.assertFalse(data["success"])

    def test_zip_upload_rejects_oversized_and_too_many_files(self):
        oversized_status, _ = self.install_upload(
            "oversized.zip",
            self.zip_bytes(
                {
                    "SKILL.md": b"x" * (main.MAX_SKILL_FILE_SIZE + 1),
                }
            ),
        )
        too_many = {
            "SKILL.md": "---\nname: many-upload\ndescription: Many files\n---\nBody",
        }
        too_many.update(
            {
                f"references/file-{idx:03}.txt": "x"
                for idx in range(main.MAX_SKILL_PACKAGE_FILES)
            }
        )
        too_many_status, _ = self.install_upload("many.zip", self.zip_bytes(too_many))

        self.assertEqual(oversized_status, 400)
        self.assertEqual(too_many_status, 400)

    def test_zip_upload_rejects_symlink_entries(self):
        status, data = self.install_upload("symlink.zip", self.zip_with_symlink())

        self.assertEqual(status, 400)
        self.assertIn("unsupported file type", data["error"])

    def test_management_toggle_trust_and_delete_update_config_and_disk(self):
        self.write_config(
            {"managed-skill": self.skill_entry("managed-skill", enabled=True)}
        )
        self.write_skill(
            "managed-skill",
            "---\nname: managed-skill\ndescription: Managed\n---\nBody",
        )

        toggle_status, toggle_data = self.api_result(
            asyncio.run(
                main.toggle_skill(
                    "managed-skill",
                    main.SkillToggleRequest(enabled=False),
                )
            )
        )
        trust_status, trust_data = self.api_result(
            asyncio.run(
                main.trust_skill(
                    "managed-skill",
                    main.SkillTrustRequest(trusted=True),
                )
            )
        )
        delete_status, delete_data = self.api_result(
            asyncio.run(main.delete_skill("managed-skill"))
        )

        self.assertEqual(toggle_status, 200)
        self.assertFalse(toggle_data["skill"]["enabled"])
        self.assertEqual(trust_status, 200)
        self.assertTrue(trust_data["skill"]["trusted"])
        self.assertEqual(delete_status, 200)
        self.assertEqual(delete_data["deleted"], "managed-skill")
        self.assertEqual(main.load_skill_config()["skills"], {})
        self.assertFalse(
            os.path.exists(os.path.join(main.SKILLS_INSTALLED_DIR, "managed-skill"))
        )

    def test_management_returns_404_for_missing_config_entry(self):
        self.write_config({})

        toggle_status, _ = self.api_result(
            asyncio.run(
                main.toggle_skill(
                    "missing-skill",
                    main.SkillToggleRequest(enabled=False),
                )
            )
        )
        trust_status, _ = self.api_result(
            asyncio.run(
                main.trust_skill(
                    "missing-skill",
                    main.SkillTrustRequest(trusted=True),
                )
            )
        )
        delete_status, _ = self.api_result(
            asyncio.run(main.delete_skill("missing-skill"))
        )

        self.assertEqual(toggle_status, 404)
        self.assertEqual(trust_status, 404)
        self.assertEqual(delete_status, 404)

    def test_delete_cleans_config_when_directory_is_missing(self):
        self.write_config(
            {"missing-dir": self.skill_entry("missing-dir", enabled=True)}
        )

        status, data = self.api_result(asyncio.run(main.delete_skill("missing-dir")))

        self.assertEqual(status, 200)
        self.assertEqual(data["warning"], "Skill directory was already missing")
        self.assertEqual(main.load_skill_config()["skills"], {})

    def test_github_url_parse_accepts_supported_forms_and_rejects_unsupported(self):
        cases = [
            ("https://raw.githubusercontent.com/acme/skills/main/pdf/SKILL.md", "raw"),
            ("https://github.com/acme/skills/blob/main/pdf/SKILL.md", "blob"),
            ("https://github.com/acme/skills/tree/main/pdf", "tree"),
        ]
        for url, kind in cases:
            with self.subTest(url=url):
                self.assertEqual(main.parse_github_skill_url(url)["kind"], kind)

        for url in (
            "http://github.com/acme/skills/blob/main/SKILL.md",
            "https://example.com/acme/skills/blob/main/SKILL.md",
            "https://github.com/acme/skills",
        ):
            with self.subTest(url=url):
                with self.assertRaises(main.SkillInstallError):
                    main.parse_github_skill_url(url)

    def test_github_blob_install_uses_contents_api_without_network(self):
        skill_text = b"---\nname: github-blob\ndescription: GitHub blob\n---\nBody"
        self.patch_github(
            contents={
                ("acme", "skills", "pdf/SKILL.md", "main"): {
                    "type": "file",
                    "path": "pdf/SKILL.md",
                    "size": len(skill_text),
                    "download_url": "https://download.test/blob",
                },
            },
            downloads={"https://download.test/blob": skill_text},
        )

        status, data = self.api_result(
            asyncio.run(
                main.install_skill(
                    main.SkillInstallRequest(
                        source_url="https://github.com/acme/skills/blob/main/pdf/SKILL.md",
                    )
                )
            )
        )

        self.assertEqual(status, 200)
        self.assertEqual(data["skill"]["name"], "github-blob")
        self.assertEqual(data["skill"]["source"]["owner"], "acme")
        self.assertEqual(data["skill"]["source"]["path"], "pdf/SKILL.md")

    def test_github_raw_install_uses_contents_api_without_network(self):
        skill_text = b"---\nname: github-raw\ndescription: GitHub raw\n---\nBody"
        self.patch_github(
            contents={
                ("acme", "skills", "pdf/SKILL.md", "main"): {
                    "type": "file",
                    "path": "pdf/SKILL.md",
                    "size": len(skill_text),
                    "download_url": "https://download.test/raw",
                },
            },
            downloads={"https://download.test/raw": skill_text},
        )

        status, data = self.api_result(
            asyncio.run(
                main.install_skill(
                    main.SkillInstallRequest(
                        source_url="https://raw.githubusercontent.com/acme/skills/main/pdf/SKILL.md",
                    )
                )
            )
        )

        self.assertEqual(status, 200)
        self.assertEqual(data["skill"]["name"], "github-raw")
        self.assertEqual(data["skill"]["source"]["ref"], "main")

    def test_github_tree_install_downloads_only_allowed_paths(self):
        skill_text = b"---\nname: github-tree\ndescription: GitHub tree\n---\nBody"
        script_text = b"print('ok')"
        self.patch_github(
            contents={
                ("acme", "skills", "pdf", "main"): [
                    {
                        "type": "file",
                        "path": "pdf/SKILL.md",
                        "size": len(skill_text),
                        "download_url": "https://download.test/skill",
                    },
                    {
                        "type": "file",
                        "path": "pdf/README.md",
                        "size": 6,
                        "download_url": "https://download.test/readme",
                    },
                    {"type": "dir", "path": "pdf/scripts"},
                ],
                ("acme", "skills", "pdf/scripts", "main"): [
                    {
                        "type": "file",
                        "path": "pdf/scripts/run.py",
                        "size": len(script_text),
                        "download_url": "https://download.test/script",
                    }
                ],
            },
            downloads={
                "https://download.test/skill": skill_text,
                "https://download.test/script": script_text,
            },
        )

        status, data = self.api_result(
            asyncio.run(
                main.install_skill(
                    main.SkillInstallRequest(
                        source_url="https://github.com/acme/skills/tree/main/pdf",
                    )
                )
            )
        )

        self.assertEqual(status, 200)
        self.assertEqual(data["skill"]["resources"]["count"], 1)
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    main.SKILLS_INSTALLED_DIR,
                    "github-tree",
                    "scripts",
                    "run.py",
                )
            )
        )
        self.assertFalse(
            os.path.exists(
                os.path.join(
                    main.SKILLS_INSTALLED_DIR,
                    "github-tree",
                    "README.md",
                )
            )
        )

    def test_github_tree_rejects_total_package_size_over_limit(self):
        original_limit = main.MAX_SKILL_PACKAGE_SIZE
        main.MAX_SKILL_PACKAGE_SIZE = 50
        self.addCleanup(lambda: setattr(main, "MAX_SKILL_PACKAGE_SIZE", original_limit))

        skill_text = b"---\nname: github-large\ndescription: GitHub large\n---\nBody"
        self.patch_github(
            contents={
                ("acme", "skills", "large", "main"): [
                    {
                        "type": "file",
                        "path": "large/SKILL.md",
                        "size": len(skill_text),
                        "download_url": "https://download.test/large-skill",
                    },
                ],
            },
            downloads={"https://download.test/large-skill": skill_text},
        )

        status, data = self.api_result(
            asyncio.run(
                main.install_skill(
                    main.SkillInstallRequest(
                        source_url="https://github.com/acme/skills/tree/main/large",
                    )
                )
            )
        )

        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "Skill package exceeds maximum size")

    def test_github_tree_repo_root_is_rejected(self):
        self.patch_github(contents={}, downloads={})

        status, data = self.api_result(
            asyncio.run(
                main.install_skill(
                    main.SkillInstallRequest(
                        source_url="https://github.com/acme/skills/tree/main",
                    )
                )
            )
        )

        self.assertEqual(status, 400)
        self.assertFalse(data["success"])

    def test_github_rejects_ambiguous_ref_path(self):
        skill_text = b"---\nname: github-raw\ndescription: GitHub raw\n---\nBody"
        self.patch_github(
            contents={
                ("acme", "skills", "pdf/SKILL.md", "main"): {
                    "type": "file",
                    "path": "pdf/SKILL.md",
                    "size": len(skill_text),
                    "download_url": "https://download.test/raw",
                },
                ("acme", "skills", "SKILL.md", "main/pdf"): {
                    "type": "file",
                    "path": "SKILL.md",
                    "size": len(skill_text),
                    "download_url": "https://download.test/ambiguous",
                },
            },
            downloads={
                "https://download.test/raw": skill_text,
                "https://download.test/ambiguous": skill_text,
            },
        )

        status, data = self.api_result(
            asyncio.run(
                main.install_skill(
                    main.SkillInstallRequest(
                        source_url="https://raw.githubusercontent.com/acme/skills/main/pdf/SKILL.md",
                    )
                )
            )
        )

        self.assertEqual(status, 400)
        self.assertIn("ambiguous", data["error"])

    def test_list_skills_still_does_not_read_skill_body(self):
        self.write_config(
            {"large-skill": self.skill_entry("large-skill", enabled=True)}
        )
        self.write_skill("large-skill", "x" * (main.MAX_SKILL_FILE_SIZE + 1))

        status, data = self.api_result(
            asyncio.run(main.get_skills(include_disabled=True))
        )

        self.assertEqual(status, 200)
        self.assertEqual(data["skills"][0]["name"], "large-skill")
        self.assertNotIn("body", data["skills"][0])

    def test_chat_injects_active_skill_context_non_stream_without_changing_response_shape(
        self,
    ):
        self.enable_skill_manager()
        self.configure_chat(stream=False, system_prompt="Base system prompt.")
        fake_session = self.patch_chat_session()
        self.write_registered_skill(
            "pdf-skill",
            content="---\nname: pdf-skill\ndescription: PDF skill\nmetadata:\n  display_name: PDF Skill\n---\nSECRET-SKILL-BODY",
            resources={
                "scripts/run.py": "SCRIPT-CONTENT-SHOULD-NOT-APPEAR",
                "assets/template.txt": "ASSET-CONTENT-SHOULD-NOT-APPEAR",
                "references/guide.md": "REFERENCE-CONTENT-SHOULD-NOT-APPEAR",
            },
            source={"type": "local", "path": "fixture"},
        )

        status, data = self.chat(
            {
                "message": "Use the skill",
                "active_skills": ["pdf-skill"],
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            set(data.keys()), {"chat_id", "content", "thinking", "references"}
        )
        payload = fake_session.posts[-1]["json"]
        system_content = payload["messages"][0]["content"]
        self.assertIn("Base system prompt.", system_content)
        self.assertIn(
            "Active skills are third-party workflow instructions", system_content
        )
        self.assertIn('<active_skill name="pdf-skill">', system_content)
        self.assertIn("Raw SKILL.md:", system_content)
        self.assertIn("SECRET-SKILL-BODY", system_content)
        self.assertIn("scripts/run.py", system_content)
        self.assertIn("assets/template.txt", system_content)
        self.assertIn("references/guide.md", system_content)
        self.assertNotIn("SCRIPT-CONTENT-SHOULD-NOT-APPEAR", system_content)
        self.assertNotIn("ASSET-CONTENT-SHOULD-NOT-APPEAR", system_content)
        self.assertNotIn("REFERENCE-CONTENT-SHOULD-NOT-APPEAR", system_content)

        messages = main.db.get_messages(data["chat_id"])
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].content, "Use the skill")
        self.assertEqual(messages[1].content, "assistant reply")
        self.assertNotIn("SECRET-SKILL-BODY", messages[0].content)
        self.assertNotIn("SECRET-SKILL-BODY", messages[1].content)

        activations = self.activation_rows(data["chat_id"])
        self.assertEqual(len(activations), 1)
        self.assertEqual(activations[0]["message_id"], messages[0].id)
        self.assertEqual(activations[0]["skill_name"], "pdf-skill")
        self.assertEqual(json.loads(activations[0]["source_json"])["type"], "local")

    def test_chat_active_skill_errors_are_returned_before_chat_creation(self):
        cases = [
            ({"message": "hi", "active_skills": "pdf-skill"}, 400),
            ({"message": "hi", "active_skills": ["BadName"]}, 400),
            (
                {
                    "message": "hi",
                    "active_skills": [f"skill-{idx}" for idx in range(6)],
                },
                400,
            ),
        ]

        for body, expected_status in cases:
            with self.subTest(body=body):
                status, data = self.chat(body)
                self.assertEqual(status, expected_status)
                self.assertIn("error", data)

        self.assertEqual(main.db.get_messages("missing-chat"), [])
        cursor = main.db.get_conn().cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM chats")
        self.assertEqual(cursor.fetchone()["count"], 0)

    def test_chat_rejects_active_skills_when_skill_manager_is_disabled(self):
        self.configure_chat(stream=False)
        self.write_registered_skill("pdf-skill")

        status, data = self.chat({"message": "hi", "active_skills": ["pdf-skill"]})

        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "Skill Manager plugin is not enabled")

    def test_trusted_skill_does_not_bypass_plugin_or_skill_enabled_checks(self):
        self.configure_chat(stream=False)
        self.write_registered_skill("trusted-skill", trusted=True)

        status, data = self.chat({"message": "hi", "active_skills": ["trusted-skill"]})

        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "Skill Manager plugin is not enabled")

        self.enable_skill_manager()
        self.write_registered_skill("disabled-trusted", enabled=False, trusted=True)
        status, data = self.chat(
            {"message": "hi", "active_skills": ["disabled-trusted"]}
        )

        self.assertEqual(status, 400)
        self.assertIn("disabled", data["error"])

    def test_trusted_skill_is_not_implicitly_injected_without_active_skills(self):
        self.enable_skill_manager()
        self.configure_chat(stream=False)
        fake_session = self.patch_chat_session()
        self.write_registered_skill(
            "trusted-skill",
            content="---\nname: trusted-skill\ndescription: Trusted skill\n---\nSECRET-TRUSTED-BODY",
            trusted=True,
        )

        status, data = self.chat(
            {"message": "Please answer without explicit active skills"}
        )

        self.assertEqual(status, 200)
        payload_text = json.dumps(fake_session.posts[-1]["json"], ensure_ascii=False)
        self.assertNotIn("trusted-skill", payload_text)
        self.assertNotIn("SECRET-TRUSTED-BODY", payload_text)
        self.assertEqual(self.activation_rows(data["chat_id"]), [])

    def test_allowed_tools_frontmatter_is_diagnostic_only(self):
        skill_text = "\n".join(
            [
                "---",
                "name: tool-skill",
                "description: Tool skill",
                "allowed-tools: Bash(*)",
                "---",
                "Body may mention scripts/run.py but grants no permissions.",
            ]
        )
        parsed = main.parse_skill_markdown(skill_text, expected_name="tool-skill")
        self.assertIn(
            "Unsupported frontmatter field: allowed-tools", parsed["diagnostics"]
        )
        self.assertNotIn("allowed-tools", parsed["frontmatter"])

        self.enable_skill_manager()
        self.configure_chat(stream=False)
        fake_session = self.patch_chat_session()
        self.write_registered_skill(
            "tool-skill",
            content=skill_text,
            resources={"scripts/run.py": "SCRIPT-CONTENT-SHOULD-NOT-APPEAR"},
            trusted=True,
        )

        status, _ = self.chat({"message": "hi", "active_skills": ["tool-skill"]})

        self.assertEqual(status, 200)
        payload = fake_session.posts[-1]["json"]
        system_content = payload["messages"][0]["content"]
        self.assertNotIn("tools", payload)
        self.assertIn("allowed-tools: Bash(*)", system_content)
        self.assertIn("Unsupported frontmatter field: allowed-tools", system_content)
        self.assertIn("scripts are not executed", system_content)
        self.assertNotIn("SCRIPT-CONTENT-SHOULD-NOT-APPEAR", system_content)

    def test_chat_rejects_missing_disabled_and_mismatched_active_skills(self):
        self.enable_skill_manager()

        status, data = self.chat({"message": "hi", "active_skills": ["missing-skill"]})
        self.assertEqual(status, 404)
        self.assertIn("Skill not found", data["error"])

        self.write_registered_skill("disabled-skill", enabled=False)
        status, data = self.chat({"message": "hi", "active_skills": ["disabled-skill"]})
        self.assertEqual(status, 400)
        self.assertIn("disabled", data["error"])

        entry = self.skill_entry("mismatch-skill", enabled=True)
        self.write_config({"mismatch-skill": entry})
        self.write_skill(
            "mismatch-skill",
            "---\nname: other-skill\ndescription: Wrong name\n---\nBody",
        )
        status, data = self.chat({"message": "hi", "active_skills": ["mismatch-skill"]})
        self.assertEqual(status, 400)
        self.assertIn("does not match", data["error"])

    def test_chat_includes_non_blocking_skill_diagnostics(self):
        self.enable_skill_manager()
        self.configure_chat(stream=False)
        fake_session = self.patch_chat_session()
        self.write_registered_skill(
            "diagnostic-skill",
            content="---\nname: diagnostic-skill\n---\nBody with missing description",
            diagnostics=["Stored install diagnostic"],
        )

        status, _ = self.chat(
            {
                "message": "hi",
                "active_skills": ["diagnostic-skill"],
            }
        )

        self.assertEqual(status, 200)
        system_content = fake_session.posts[-1]["json"]["messages"][0]["content"]
        self.assertIn('<active_skill name="diagnostic-skill">', system_content)
        self.assertIn("Stored install diagnostic", system_content)
        self.assertIn("Missing required field: description", system_content)
        self.assertIn("Body with missing description", system_content)

    def test_chat_deduplicates_active_skills_preserving_order(self):
        self.enable_skill_manager()
        self.configure_chat(stream=False)
        fake_session = self.patch_chat_session()
        self.write_config(
            {
                "second-skill": self.skill_entry("second-skill", enabled=True),
                "first-skill": self.skill_entry("first-skill", enabled=True),
            }
        )
        self.write_skill(
            "second-skill",
            "---\nname: second-skill\ndescription: Second\n---\nSecond body",
        )
        self.write_skill(
            "first-skill",
            "---\nname: first-skill\ndescription: First\n---\nFirst body",
        )

        status, _ = self.chat(
            {
                "message": "hi",
                "active_skills": ["second-skill", "first-skill", "second-skill"],
            }
        )

        self.assertEqual(status, 200)
        system_content = fake_session.posts[-1]["json"]["messages"][0]["content"]
        self.assertEqual(system_content.count('<active_skill name="second-skill">'), 1)
        self.assertLess(
            system_content.index('<active_skill name="second-skill">'),
            system_content.index('<active_skill name="first-skill">'),
        )

    def test_chat_system_prompt_skill_and_compaction_summary_order(self):
        self.enable_skill_manager()
        self.enable_context_compressor(auto_compress=False)
        self.configure_chat(stream=False, system_prompt="Base system prompt.")
        fake_session = self.patch_chat_session()
        self.write_registered_skill(
            "summary-skill",
            content="---\nname: summary-skill\ndescription: Summary\n---\nSECRET-SKILL-BODY",
        )
        chat_obj = main.db.create_chat("Existing")
        main.db.add_message(chat_obj.id, "user", "old user")
        boundary = main.db.add_message(chat_obj.id, "assistant", "old assistant")
        main.db.add_message(chat_obj.id, "user", "recent user")
        main.db.save_chat_compaction(
            chat_obj.id,
            "COMPACT SUMMARY",
            boundary,
            original_token_estimate=100,
            summary_token_estimate=10,
            compressed_message_count=2,
        )

        status, _ = self.chat(
            {
                "chat_id": chat_obj.id,
                "message": "new user",
                "active_skills": ["summary-skill"],
            }
        )

        self.assertEqual(status, 200)
        system_content = fake_session.posts[-1]["json"]["messages"][0]["content"]
        self.assertLess(
            system_content.index("Base system prompt."),
            system_content.index("Active skills are"),
        )
        self.assertLess(
            system_content.index("Active skills are"),
            system_content.index('<active_skill name="summary-skill">'),
        )
        self.assertLess(
            system_content.index('<active_skill name="summary-skill">'),
            system_content.index("Earlier conversation context"),
        )
        self.assertIn("COMPACT SUMMARY", system_content)
        self.assertNotIn(
            "SECRET-SKILL-BODY", main.db.get_chat_compaction(chat_obj.id)["summary"]
        )

    def test_chat_stream_injects_active_skill_before_first_stream_chunk(self):
        self.enable_skill_manager()
        self.configure_chat(stream=True)
        fake_session = self.patch_chat_session()
        self.write_registered_skill("stream-skill")

        async def call_and_collect():
            response = await main.chat(
                JsonRequest(
                    {
                        "message": "stream",
                        "active_skills": ["stream-skill"],
                    }
                )
            )
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(
                    chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                )
            return chunks

        chunks = asyncio.run(call_and_collect())

        self.assertIn('"chat_id"', chunks[0])
        system_content = fake_session.posts[-1]["json"]["messages"][0]["content"]
        self.assertIn('<active_skill name="stream-skill">', system_content)
        self.assertIn("SECRET-SKILL-BODY stream-skill", system_content)

    def test_chat_active_skill_with_rag_keeps_rag_in_last_user_message(self):
        self.enable_skill_manager()
        self.configure_chat(stream=False)
        fake_session = self.patch_chat_session()
        self.write_registered_skill("rag-skill")
        original_rag = main.llm_service.build_rag_context

        async def fake_rag(query):
            return "RAG CONTEXT\n\n", [{"title": "ref"}]

        main.llm_service.build_rag_context = fake_rag
        self.addCleanup(
            lambda: setattr(main.llm_service, "build_rag_context", original_rag)
        )

        status, _ = self.chat(
            {
                "message": "question",
                "use_rag": True,
                "active_skills": ["rag-skill"],
            }
        )

        self.assertEqual(status, 200)
        payload = fake_session.posts[-1]["json"]
        self.assertIn(
            '<active_skill name="rag-skill">', payload["messages"][0]["content"]
        )
        self.assertIn("RAG CONTEXT", payload["messages"][-1]["content"])
        self.assertIn("User question: question", payload["messages"][-1]["content"])

    def test_chat_active_skill_with_image_keeps_last_user_message_multimodal(self):
        self.enable_skill_manager()
        self.configure_chat(stream=False, vision=True)
        fake_session = self.patch_chat_session()
        self.write_registered_skill("vision-skill")

        status, _ = self.chat(
            {
                "message": "look",
                "image_base64": "abc123",
                "active_skills": ["vision-skill"],
            }
        )

        self.assertEqual(status, 200)
        payload = fake_session.posts[-1]["json"]
        self.assertIn(
            '<active_skill name="vision-skill">', payload["messages"][0]["content"]
        )
        self.assertIsInstance(payload["messages"][-1]["content"], list)
        self.assertEqual(payload["messages"][-1]["content"][0]["text"], "look")

    def test_skill_activation_audit_is_removed_on_delete_and_stale_chat_cleanup(self):
        self.enable_skill_manager()
        self.configure_chat(stream=False)
        self.patch_chat_session()
        self.write_registered_skill("audit-skill")

        status, data = self.chat(
            {
                "message": "audit",
                "active_skills": ["audit-skill"],
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(self.activation_rows(data["chat_id"])), 1)

        main.db.delete_chat(data["chat_id"])
        self.assertEqual(self.activation_rows(data["chat_id"]), [])

        old_chat = main.db.create_chat("Old")
        old_message = main.db.add_message(old_chat.id, "user", "old")
        main.db.add_skill_activations(
            old_chat.id, old_message.id, [{"name": "audit-skill", "source": {}}]
        )
        conn = main.db.get_conn()
        conn.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00", old_chat.id),
        )
        conn.commit()
        for idx in range(10):
            main.db.create_chat(f"new-{idx}")

        self.assertEqual(self.activation_rows(old_chat.id), [])

    def test_skill_routes_are_registered_before_static_mount(self):
        expected = {
            "/api/skills": "get_skills",
            "/api/skills/install": "install_skill",
            "/api/skills/upload": "upload_skill",
            "/api/skills/pdf-processing": "get_skill_detail",
            "/api/skills/pdf-processing/content": "get_skill_content",
            "/api/skills/pdf-processing/resources": "get_skill_resources",
        }

        for path, endpoint_name in expected.items():
            with self.subTest(path=path):
                method = (
                    "POST"
                    if endpoint_name in ("install_skill", "upload_skill")
                    else "GET"
                )
                route = self.first_route_match(path, method=method)
                self.assertIsNotNone(route)
                self.assertEqual(route.name, endpoint_name)


if __name__ == "__main__":
    unittest.main()
