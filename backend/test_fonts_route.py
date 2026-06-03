import os
import shutil
import sys
import tempfile
import unittest
from urllib.parse import unquote

TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-font-route-test-")
os.environ["DATA_DIR"] = TEST_DATA_DIR

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend import main  # noqa: E402


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class FontRouteTests(unittest.TestCase):
    def test_resolve_font_path_allows_existing_font(self):
        font_path = main.resolve_font_path("remixicon/remixicon.woff2")

        self.assertTrue(font_path.is_file())
        self.assertEqual(font_path.name, "remixicon.woff2")
        self.assertTrue(font_path.is_relative_to(main.FONT_DIR))

    def test_resolve_font_path_rejects_parent_directory_escape(self):
        for path in (
            "../../main.py",
            unquote("%2e%2e/%2e%2e/main.py"),
            "../../../README.md",
        ):
            with self.subTest(path=path):
                with self.assertRaises(main.HTTPException) as context:
                    main.resolve_font_path(path)
                self.assertEqual(context.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
