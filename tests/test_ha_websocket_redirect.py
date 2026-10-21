"""Real HA WebSocket boundaries, using only loopback and synthetic credentials."""
import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from aiohttp import ClientError, web, WSMsgType

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ha_zha
from test_strict_tls import chain


class HaWebSocketTests(unittest.IsolatedAsyncioTestCase):
    TOKEN = "synthetic-websocket-token"
    ENTRIES = "/api/config/config_entries/entry"

    @classmethod
    def setUpClass(cls):
        cls.certificates = tempfile.TemporaryDirectory(prefix="slzb-websocket-ca-")
        cls.addClassCleanup(cls.certificates.cleanup)
        cls.certificate_dir = Path(cls.certificates.name)
        chain(cls.certificate_dir, "none")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="slzb-websocket-")
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "backup.json"
        self.messages = []
        self.websockets = set()
        self.server_errors = []
        self.addCleanup(self.assertEqual, self.server_errors, [])
        self.enterContext(patch.dict(os.environ, {
            "HA_TOKEN": self.TOKEN,
            "SSL_CERT_FILE": str(self.certificate_dir / "root.pem"),
            "SLZB_TLS_SECURITY_LEVEL": "3",
        }))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def server_context(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.certificate_dir / "chain.pem", self.certificate_dir / "leaf.key")
        return context

    async def endpoint(self, routes, *, tls=False):
        requests = []

        @web.middleware
        async def record(request, handler):
            requests.append((request.path, request.headers.get("Authorization")))
            return await handler(request)

        async def entries(_):
            return web.json_response([])

        application = web.Application(middlewares=[record])
        application.router.add_get(self.ENTRIES, entries)
        for path, handler in routes.items():
            application.router.add_get(path, handler)
        runner = web.AppRunner(application, shutdown_timeout=0.2)
        async def cleanup():
            for socket in tuple(self.websockets):
                await asyncio.wait_for(socket.close(), 1)
            await asyncio.wait_for(runner.cleanup(), 2)

        self.addAsyncCleanup(cleanup)
        await asyncio.wait_for(runner.setup(), 2)
        site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=self.server_context() if tls else None)
        await asyncio.wait_for(site.start(), 2)
        port = runner.addresses[0][1]
        return f"{'https' if tls else 'http'}://127.0.0.1:{port}", requests

    def socket_handler(self, *, greeting=None, silent=None):
        greeting = {"type": "auth_required"} if greeting is None else greeting

        async def receive(socket):
            message = await socket.receive(timeout=2)
            if message.type != WSMsgType.TEXT:
                return None
            value = json.loads(message.data)
            self.messages.append(value)
            return value

        async def handler(request):
            socket = web.WebSocketResponse()
            self.websockets.add(socket)
            try:
                async with asyncio.timeout(3):
                    await socket.prepare(request)
                    if silent == "before-auth":
                        await receive(socket)
                        return socket
                    if isinstance(greeting, str):
                        await socket.send_str(greeting)
                    else:
                        await socket.send_json(greeting)
                    if await receive(socket) is None:
                        return socket
                    if silent == "after-auth":
                        await receive(socket)
                        return socket
                    await socket.send_json({"type": "auth_ok"})
                    results = ({"is_complete": True, "backup": {"network_info": {}}}, {"channel": 15})
                    for result in results:
                        message = await receive(socket)
                        if message is None:
                            return socket
                        await socket.send_json({"id": message["id"], "success": True, "result": result})
            except Exception as error:
                self.server_errors.append(type(error).__name__)
                raise
            finally:
                await asyncio.wait_for(socket.close(), 1)
                self.websockets.discard(socket)
            return socket

        return handler

    @staticmethod
    def redirect(location, status=302):
        async def handler(_):
            return web.Response(status=status, headers={"Location": location()})
        return handler

    async def run_backup(self, url):
        args = SimpleNamespace(url=url, action="backup", out=self.output)
        return await asyncio.wait_for(ha_zha.run(args), 2)

    async def rejected_backup(self, url):
        with self.assertRaises((ValueError, RuntimeError, ClientError)):
            await self.run_backup(url)
        self.assertFalse(self.output.exists())

    async def test_direct_trusted_https_authenticates_and_saves_private_backup(self):
        url, requests = await self.endpoint({"/api/websocket": self.socket_handler()}, tls=True)
        await self.run_backup(url)
        self.assertEqual([path for path, _ in requests], [self.ENTRIES, "/api/websocket"])
        self.assertTrue(all(auth == "Bearer " + self.TOKEN for _, auth in requests))
        self.assertEqual(self.messages, [
            {"type": "auth", "access_token": self.TOKEN},
            {"id": 1, "type": "zha/network/backups/create"},
            {"id": 2, "type": "zha/network/settings"},
        ])
        self.assertEqual(json.loads(self.output.read_text()), {
            "is_complete": True, "backup": {"network_info": {}}, "settings": {"channel": 15},
        })
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    async def assert_redirect_rejected(self, *, same_origin=False, downgrade=False, return_chain=False, status=302):
        destination = {}
        if same_origin:
            url, requests = await self.endpoint({
                "/api/websocket": self.redirect(lambda: "/redirected"),
                "/redirected": self.socket_handler(),
            })
            target_requests = requests
        else:
            target_routes = ({"/redirected": self.redirect(lambda: destination["origin"] + "/returned")}
                             if return_chain else {"/redirected": self.socket_handler()})
            target, target_requests = await self.endpoint(target_routes)
            url, requests = await self.endpoint({
                "/api/websocket": self.redirect(lambda: target + "/redirected", status=status),
                "/returned": self.socket_handler(),
            }, tls=downgrade)
            destination["origin"] = url
        try:
            await self.rejected_backup(url)
        finally:
            self.assertEqual([path for path, _ in requests], [self.ENTRIES, "/api/websocket"])
            if not same_origin:
                self.assertEqual(target_requests, [])
            self.assertEqual(self.messages, [])

    async def test_cross_origin_redirect_never_requests_target(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.messages.clear()
                self.output.unlink(missing_ok=True)
                await self.assert_redirect_rejected(status=status)

    async def test_same_origin_path_redirect_never_requests_target(self):
        await self.assert_redirect_rejected(same_origin=True)

    async def test_trusted_https_redirect_never_requests_plaintext_target(self):
        await self.assert_redirect_rejected(downgrade=True)

    async def test_redirect_chain_returning_to_origin_is_rejected_at_first_hop(self):
        await self.assert_redirect_rejected(return_chain=True)

    async def test_unexpected_greetings_never_receive_auth_frame(self):
        for greeting in ({"type": "auth_ok"}, [], "not valid JSON"):
            with self.subTest(greeting=greeting):
                self.messages.clear()
                self.output.unlink(missing_ok=True)
                url, _ = await self.endpoint({"/api/websocket": self.socket_handler(greeting=greeting)})
                try:
                    await self.rejected_backup(url)
                finally:
                    self.assertEqual(self.messages, [])

    async def assert_auth_timeout(self, stage):
        url, _ = await self.endpoint({"/api/websocket": self.socket_handler(silent=stage)})
        args = SimpleNamespace(url=url, action="backup", out=self.output)
        with patch.object(ha_zha, "AUTH_TIMEOUT", 0.05, create=True):
            task = asyncio.create_task(ha_zha.run(args))
            try:
                with self.assertRaises(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(task), 0.75)
                self.assertTrue(task.done(), "Only the outer watchdog expired; authentication has no deadline")
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 1)
        expected = [] if stage == "before-auth" else [{"type": "auth", "access_token": self.TOKEN}]
        self.assertEqual(self.messages, expected)
        self.assertFalse(self.output.exists())

    async def test_silent_server_before_auth_required_hits_internal_deadline(self):
        await self.assert_auth_timeout("before-auth")

    async def test_silent_server_after_auth_hits_internal_deadline(self):
        await self.assert_auth_timeout("after-auth")


if __name__ == "__main__":
    unittest.main()
