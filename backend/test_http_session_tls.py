import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import ANY, AsyncMock, Mock, patch

TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-http-session-test-")
os.environ["DATA_DIR"] = TEST_DATA_DIR

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend import main  # noqa: E402


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class HTTPSessionTLSTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        main._http_session = None

    async def asyncTearDown(self):
        await main.close_http_session()

    def test_create_ssl_context_uses_certifi_cafile(self):
        ssl_context = object()

        with patch.object(main.certifi, "where", return_value="/tmp/certifi.pem") as certifi_where, \
                patch.object(main.ssl, "create_default_context", return_value=ssl_context) as create_context:
            result = main._create_ssl_context()

        self.assertIs(result, ssl_context)
        certifi_where.assert_called_once_with()
        create_context.assert_called_once_with(cafile="/tmp/certifi.pem")

    async def test_get_http_session_creates_connector_with_certifi_ssl_context_and_reuses_session(self):
        ssl_context = object()
        connector = object()
        fake_session = Mock()
        fake_session.closed = False
        fake_session.close = AsyncMock()

        with patch.object(main, "_create_ssl_context", return_value=ssl_context) as create_ssl_context, \
                patch.object(main.aiohttp, "TCPConnector", return_value=connector) as tcp_connector, \
                patch.object(main.aiohttp, "ClientSession", return_value=fake_session) as client_session:
            first = await main.get_http_session()
            second = await main.get_http_session()

        self.assertIs(first, fake_session)
        self.assertIs(second, fake_session)
        create_ssl_context.assert_called_once_with()
        tcp_connector.assert_called_once_with(ssl=ssl_context)
        client_session.assert_called_once_with(timeout=ANY, connector=connector)

    async def test_close_http_session_closes_open_session_and_clears_global(self):
        fake_session = Mock()
        fake_session.closed = False
        fake_session.close = AsyncMock()
        main._http_session = fake_session

        await main.close_http_session()

        fake_session.close.assert_awaited_once_with()
        self.assertIsNone(main._http_session)

    async def test_close_http_session_clears_already_closed_session_without_closing_again(self):
        fake_session = Mock()
        fake_session.closed = True
        fake_session.close = AsyncMock()
        main._http_session = fake_session

        await main.close_http_session()

        fake_session.close.assert_not_awaited()
        self.assertIsNone(main._http_session)


if __name__ == "__main__":
    unittest.main()
