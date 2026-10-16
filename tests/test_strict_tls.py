"""Real transport regressions use only synthetic certificates and loopback."""
import asyncio
import contextlib
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
from types import SimpleNamespace
from urllib.error import URLError

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_firmware
import ha_zha
import slzb
import tls_policy

def command(directory, *args):
    subprocess.run(["openssl", *args], cwd=directory, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)


def chain(directory, weak):
    # 2047 differs from the rounded strength estimate accepted at level 2.
    for name in ("root", "intermediate", "leaf"):
        bits = "2047" if name == weak else "3072"
        command(directory, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:" + bits,
                "-out", name + ".key")
        command(directory, "req", "-new", "-key", name + ".key", "-out", name + ".csr", "-subj", "/CN=" + name)
        ca = name != "leaf"
        (directory / (name + ".ext")).write_text(
            "basicConstraints=critical,CA:" + ("TRUE" if ca else "FALSE") + "\n" +
            ("keyUsage=critical,keyCertSign,cRLSign\n" if ca else
             "keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:127.0.0.1\n"))
        issuer = "root" if name != "leaf" else "intermediate"
        signing = ["-signkey", "root.key"] if name == "root" else ["-CA", issuer + ".pem", "-CAkey", issuer + ".key"]
        command(directory, "x509", "-req", "-in", name + ".csr", *signing,
                "-set_serial", str(("root", "intermediate", "leaf").index(name) + 1),
                "-days", "1", "-sha256", "-extfile", name + ".ext", "-out", name + ".pem")
    (directory / "chain.pem").write_bytes((directory / "leaf.pem").read_bytes() +
                                         (directory / "intermediate.pem").read_bytes())


class StrictTlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="slzb-tls-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        for weak in ("none", "leaf", "intermediate", "root"):
            path = cls.directory / weak
            path.mkdir()
            chain(path, weak)
        image = b":00000001FF\n"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(fetch_firmware.NAME + ".hex", image)
        cls.archive = buffer.getvalue()
        cls.image = image

    @contextlib.contextmanager
    def endpoint(self, weak, tls):
        path = self.directory / weak
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.set_ciphers("DEFAULT:@SECLEVEL=0")  # Test peer only.
        context.minimum_version = context.maximum_version = tls
        context.load_cert_chain(path / "chain.pem", path / "leaf.key")
        requests = []
        archive = self.archive
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                requests.append((self.path, self.headers.get("Authorization")))
                payload = archive if self.path == "/firmware.zip" else b"[]"
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Content-Type", "application/zip" if self.path == "/firmware.zip" else "application/json")
                self.send_header("respValuesArr", '{"hwRev":"SLZB-06"}')
                self.end_headers()
                self.wfile.write(payload)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.dict(os.environ, {"SSL_CERT_FILE": str(path / "root.pem"),
                                        "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1",
                                        "SLZB_TLS_SECURITY_LEVEL": "3", "HA_TOKEN": "synthetic-only"}):
                yield "https://127.0.0.1:" + str(server.server_port), requests
        finally:
            server.shutdown(); server.server_close(); worker.join()

    def test_actual_transports_reject_weak_chain_before_request_or_output(self):
        for tls in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
            for weak in ("none", "leaf", "intermediate", "root"):
                with self.subTest(tls=tls, weak=weak), self.endpoint(weak, tls) as (url, requests):
                    with tempfile.TemporaryDirectory() as temporary:
                        out = Path(temporary) / "output"
                        def firmware():
                            with patch.object(fetch_firmware, "URL", url + "/firmware.zip"), \
                                 patch.object(fetch_firmware, "ARCHIVE_SHA256", hashlib.sha256(self.archive).hexdigest()), \
                                 patch.object(fetch_firmware, "HEX_SHA256", hashlib.sha256(self.image).hexdigest()), \
                                 patch.object(sys, "argv", ["fetch_firmware", "--out", str(out)]):
                                fetch_firmware.main()
                        def home_assistant():
                            asyncio.run(ha_zha.run(SimpleNamespace(url=url, action="status")))
                        for operation in (lambda: slzb.status(url), firmware, home_assistant):
                            with self.subTest(operation=operation.__name__), contextlib.redirect_stdout(io.StringIO()):
                                if weak == "none": operation()
                                else:
                                    with self.assertRaises((URLError, aiohttp.ClientConnectorCertificateError)):
                                        operation()
                        if weak == "none":
                            self.assertEqual(len(requests), 3)
                            self.assertEqual((out / (fetch_firmware.NAME + ".hex")).read_bytes(), self.image)
                            self.assertEqual(requests[-1][1], "Bearer synthetic-only")
                        else:
                            self.assertEqual(requests, [])
                            self.assertFalse(out.exists())

    def test_firmware_redirect_handler_refuses_plaintext(self):
        from email.message import Message
        from urllib.request import Request
        handler = fetch_firmware.HttpsOnlyRedirect()
        request = Request("https://firmware.example/archive.zip")
        with self.assertRaisesRegex(ValueError, "remain HTTPS"):
            handler.redirect_request(request, None, 302, "Found", Message(), "http://firmware.example/archive.zip")
        self.assertEqual(handler.redirect_request(request, None, 302, "Found", Message(),
            "https://cdn.example/archive.zip").full_url, "https://cdn.example/archive.zip")

    def test_normal_hostname_and_ca_checks_remain_enabled(self):
        with self.endpoint("none", ssl.TLSVersion.TLSv1_3) as (url, requests):
            with self.assertRaises(URLError):
                slzb.status(url.replace("127.0.0.1", "localhost"))
            with patch.dict(os.environ, {"SSL_CERT_FILE": str(self.directory / "root/root.pem")}):
                with self.assertRaises(URLError):
                    slzb.status(url)
            self.assertEqual(requests, [])

    def test_websocket_rechecks_its_peer_before_authentication(self):
        from aiohttp import web
        async def run(weak, tls):
            strong = self.directory / "none"
            peer = self.directory / weak
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.set_ciphers("DEFAULT:@SECLEVEL=0")  # Synthetic server only.
            context.minimum_version = context.maximum_version = tls
            context.load_cert_chain(strong / "chain.pem", strong / "leaf.key")
            ws_requests, auth_messages = [], []
            async def entries(request):
                context.load_cert_chain(peer / "chain.pem", peer / "leaf.key")
                response = web.json_response([])
                response.force_close()  # The WSS request must make a fresh handshake.
                return response
            async def socket(request):
                ws_requests.append(request.headers.get("Authorization"))
                ws = web.WebSocketResponse()
                await ws.prepare(request)
                await ws.send_json({"type": "auth_required"})
                auth_messages.append(await ws.receive_json())
                await ws.send_json({"type": "auth_ok"})
                for result in ({"is_complete": True, "backup": {"network_info": {}}}, {}):
                    message = await ws.receive_json()
                    await ws.send_json({"id": message["id"], "success": True, "result": result})
                await ws.close()
                return ws
            app = web.Application()
            app.router.add_get("/api/config/config_entries/entry", entries)
            app.router.add_get("/api/websocket", socket)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            try:
                with tempfile.TemporaryDirectory() as temporary:
                    trust = Path(temporary) / "trust.pem"
                    trust.write_bytes((strong / "root.pem").read_bytes() + (peer / "root.pem").read_bytes())
                    output = Path(temporary) / "backup.json"
                    with patch.dict(os.environ, {"SSL_CERT_FILE": str(trust), "SLZB_TLS_SECURITY_LEVEL": "3",
                                                "HA_TOKEN": "synthetic-only"}), contextlib.redirect_stdout(io.StringIO()):
                        args = SimpleNamespace(url=f"https://127.0.0.1:{port}", action="backup", out=output)
                        if weak == "none":
                            await ha_zha.run(args)
                            self.assertTrue(json.loads(output.read_text())["is_complete"])
                            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                            self.assertEqual(auth_messages, [{"type": "auth", "access_token": "synthetic-only"}])
                        else:
                            with self.assertRaises(aiohttp.ClientConnectorCertificateError):
                                await ha_zha.run(args)
                            self.assertFalse(output.exists())
                            self.assertEqual(ws_requests, [])
                            self.assertEqual(auth_messages, [])
            finally:
                await runner.cleanup()
        for tls in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
            for weak in ("none", "leaf", "intermediate", "root"):
                with self.subTest(tls=tls, weak=weak):
                    asyncio.run(run(weak, tls))

    def test_policy_validates_option_and_preserves_platform_security(self):
        with patch.dict(os.environ, {"SLZB_TLS_SECURITY_LEVEL": "1"}):
            with self.assertRaises(ValueError): tls_policy.client_context()
        with patch.dict(os.environ, {"SLZB_TLS_SECURITY_LEVEL": "3"}):
            context = tls_policy.client_context()
            self.assertGreaterEqual(context.security_level, 3)
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        with patch.dict(os.environ, {"SLZB_TLS_SECURITY_LEVEL": "2"}):
            with patch.object(tls_policy.ssl, "create_default_context", return_value=context):
                self.assertEqual(tls_policy.client_context().security_level, 3)


if __name__ == "__main__":
    unittest.main()
