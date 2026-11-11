"""Legacy Hermes migration/security regressions; execution now belongs to Runner."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

PREVIOUS_DATA_DIR = os.environ.get("DATA_DIR")
TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-hermes-migration-")
os.environ["DATA_DIR"] = TEST_DATA_DIR
from backend import main


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
    if PREVIOUS_DATA_DIR is None:
        os.environ.pop("DATA_DIR", None)
    else:
        os.environ["DATA_DIR"] = PREVIOUS_DATA_DIR


class RequestStub:
    url = "http://chatraw.local/api/agents/runs"

    def __init__(self, headers):
        self.headers = headers


class HermesMigrationTests(unittest.TestCase):
    def test_same_origin_and_fetch_metadata_are_required(self):
        for headers in (
            {"origin": "http://chatraw.local"},
            {"sec-fetch-site": "same-origin"},
            {"referer": "http://chatraw.local/chat"},
        ):
            main.validate_agent_request_origin(RequestStub(headers))
        for headers in (
            {},
            {"origin": "http://evil.example"},
            {"sec-fetch-site": "cross-site"},
        ):
            with self.subTest(headers=headers), self.assertRaises(HTTPException):
                main.validate_agent_request_origin(RequestStub(headers))

    def test_cors_wildcard_is_not_control_plane_authorization(self):
        with patch.object(main, "CORS_ORIGINS", "*"):
            with self.assertRaises(HTTPException):
                main.validate_agent_request_origin(
                    RequestStub({"origin": "http://evil.example"})
                )

    def test_explicit_cors_origin_is_still_supported(self):
        with patch.object(main, "CORS_ORIGINS", "http://allowed.example"):
            main.validate_agent_request_origin(
                RequestStub({"origin": "http://allowed.example"})
            )

    def test_legacy_runtime_is_absent_from_production_module(self):
        for name in (
            "_active_hermes_runs",
            "_consume_hermes_run",
            "hermes_chat",
            "hermes_run_approval",
        ):
            self.assertFalse(hasattr(main, name), name)


if __name__ == "__main__":
    unittest.main()
