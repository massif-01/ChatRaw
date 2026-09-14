"""Verify the read-aloud plugin's JSON contract through the real host proxy.

The upstream is mocked; no real keys, network requests, or cloud charges.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

_TEST_DATA = tempfile.TemporaryDirectory(prefix="chatraw-read-aloud-test-")
os.environ["DATA_DIR"] = _TEST_DATA.name
from backend import main  # noqa: E402


class UpstreamResponse:
    def __init__(self, status, data):
        self.status, self.data = status, data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def json(self):
        return self.data


class ReadAloudProxyTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, status, data):
        response = UpstreamResponse(status, data)
        session = unittest.mock.Mock()
        session.request.return_value = response
        request = main.ProxyRequest(
            service_id="aliyun-qwen-tts",
            url="https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
            body={
                "model": "qwen3-tts-flash",
                "input": {
                    "text": "这是朗读测试。",
                    "voice": "Cherry",
                    "language_type": "Auto",
                },
            },
        )
        with patch.object(
            main, "get_http_session", AsyncMock(return_value=session)
        ), patch.object(
            main,
            "load_plugin_config",
            return_value={
                "api_keys": {"aliyun-qwen-tts": "test-secret-only-on-server"}
            },
        ):
            result = await main.proxy_request(request)
        return result, session.request.call_args.kwargs

    async def test_key_is_added_only_to_upstream_and_audio_metadata_is_preserved(self):
        data = {
            "output": {
                "audio": {
                    "url": "https://example.invalid/test.wav",
                    "expires_at": 2000000000,
                }
            }
        }
        result, sent = await self.invoke(200, data)
        self.assertEqual(
            sent["headers"]["Authorization"], "Bearer test-secret-only-on-server"
        )
        self.assertEqual(sent["json"]["input"]["text"], "这是朗读测试。")
        self.assertFalse(sent["allow_redirects"])
        self.assertEqual(result, {"success": True, "data": data})
        self.assertNotIn("test-secret", json.dumps(result))

    async def test_provider_error_is_preserved_for_user_feedback(self):
        result, _sent = await self.invoke(
            401, {"code": "InvalidApiKey", "message": "API key invalid"}
        )
        self.assertEqual(result.status_code, 401)
        body = json.loads(result.body)
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "InvalidApiKey")
        self.assertNotIn("test-secret", result.body.decode())


if __name__ == "__main__":
    unittest.main()
