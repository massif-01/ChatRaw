import json
import tempfile
import unittest
from pathlib import Path

from backend.bundled_plugins import BundledPluginError, install


class BundledPluginsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.market = self.root / "market"
        self.installed = self.root / "installed"
        self.source = self.market / "official"
        (self.source / "lib" / "fonts").mkdir(parents=True)
        (self.market / "index.json").write_text(
            json.dumps({"plugins": [{"id": "official", "folder": "official"}]})
        )
        (self.source / "manifest.json").write_text('{"id":"official","main":"main.js"}')
        (self.source / "main.js").write_text("official code")
        (self.source / "lib" / "fonts" / "math.woff2").write_bytes(b"font data")
        self.config = {
            "plugins": {
                "official": {"enabled": False, "settings_values": {"theme": "saved"}}
            }
        }
        self.saved = []

    def tearDown(self):
        self.temp.cleanup()

    def test_entire_bundle_and_settings_survive_install_and_reinstall(self):
        for _ in range(2):
            result = install(
                "official", self.market, self.installed, self.config, self.saved.append
            )
            self.assertTrue(result["success"])
            self.assertEqual(
                (self.installed / "official/lib/fonts/math.woff2").read_bytes(),
                b"font data",
            )
            self.assertEqual(
                self.config["plugins"]["official"],
                {"enabled": False, "settings_values": {"theme": "saved"}},
            )

    def test_unknown_id_and_paths_cannot_select_host_files(self):
        for plugin_id in ("../official", "/tmp/official", "not-bundled", None):
            with self.subTest(plugin_id=plugin_id), self.assertRaises(
                BundledPluginError
            ):
                install(
                    plugin_id,
                    self.market,
                    self.installed,
                    self.config,
                    self.saved.append,
                )
        self.assertFalse(self.installed.exists())

    def test_link_in_bundle_is_not_followed(self):
        (self.source / "leak").symlink_to(self.market / "index.json")
        with self.assertRaises(BundledPluginError):
            install(
                "official", self.market, self.installed, self.config, self.saved.append
            )

    def test_configuration_failure_restores_previous_installation(self):
        target = self.installed / "official"
        target.mkdir(parents=True)
        (target / "main.js").write_text("previous code")

        def fail(config):
            raise OSError("disk unavailable")

        with self.assertRaises(OSError):
            install("official", self.market, self.installed, self.config, fail)
        self.assertEqual((target / "main.js").read_text(), "previous code")


if __name__ == "__main__":
    unittest.main()
