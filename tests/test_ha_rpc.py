import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ha_zha import rpc


class FakeSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []

    async def send_json(self, message):
        self.sent.append(message)

    async def receive_json(self):
        return next(self.messages)


class RpcTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_matching_response(self):
        socket = FakeSocket([{"type": "event"}, {"id": 3, "success": True, "result": {"is_complete": True}}])
        result = await rpc(socket, {"id": 3, "type": "zha/network/backups/create"})
        self.assertTrue(result["is_complete"])
        self.assertEqual(len(socket.sent), 1)

    async def test_error_is_reported_without_dumping_private_payload(self):
        socket = FakeSocket([{"id": 1, "success": False, "error": {"code": "unknown_error", "message": "private details"}}])
        with self.assertRaisesRegex(RuntimeError, "unknown_error") as caught:
            await rpc(socket, {"id": 1, "type": "test"})
        self.assertNotIn("private details", str(caught.exception))

    async def test_timeout_is_bounded(self):
        class SilentSocket(FakeSocket):
            async def receive_json(self):
                await asyncio.sleep(10)
        with self.assertRaises(TimeoutError):
            await rpc(SilentSocket([]), {"id": 1, "type": "test"}, timeout=0.01)


if __name__ == "__main__":
    unittest.main()
