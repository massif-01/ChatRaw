"""Actual ASGI routes retire old Hermes controls without submitting native work."""

import os
import shutil
import tempfile
import unittest

import httpx

PREVIOUS_DATA_DIR = os.environ.get("DATA_DIR")
TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-hermes-retired-")
os.environ["DATA_DIR"] = TEST_DATA_DIR
from backend import main


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
    if PREVIOUS_DATA_DIR is None:
        os.environ.pop("DATA_DIR", None)
    else:
        os.environ["DATA_DIR"] = PREVIOUS_DATA_DIR


class HermesRetirementTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_chat_health_and_approval_are_explicitly_retired(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://testserver",
            headers={"Origin": "http://testserver"},
        ) as client:
            for method, path in (
                ("POST", "/api/hermes/chat"),
                ("GET", "/api/hermes/health"),
                ("POST", "/api/hermes/runs/opaque/native/id/approval"),
            ):
                response = await client.request(method, path)
                self.assertEqual(response.status_code, 410, response.text)
                self.assertFalse(response.json()["success"])

    async def test_retired_routes_do_not_bypass_origin_checks(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://testserver",
            headers={"Origin": "http://evil.example"},
        ) as client:
            response = await client.post("/api/hermes/chat")
            self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
