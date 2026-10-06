import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import esp32_core as core


class FakeESP:
    ESP_CMDS = {"READ_FLASH": 0xD2}

    def __init__(self, data):
        self.data = data
        self._port = types.SimpleNamespace(timeout=3)
        self.frames = []
        self.acks = []
        self.requests = []

    def check_command(self, label, command, payload):
        offset, length, packet, window = struct.unpack("<IIII", payload)
        self.requests.append((offset, length, packet, window))
        data = self.data[offset:offset + length]
        self.frames = [data[pos:pos + packet] for pos in range(0, length, packet)]
        self.frames.append(hashlib.md5(data).digest())

    def read(self):
        return self.frames.pop(0)

    def write(self, value):
        self.acks.append(struct.unpack("<I", value)[0])

    def flash_md5sum(self, offset, length):
        return hashlib.md5(self.data[offset:offset + length]).hexdigest()


class CoreTests(unittest.TestCase):
    def test_integer_zero_security_state_matches_real_esptool_api(self):
        chip = types.SimpleNamespace(
            CHIP_NAME="ESP32", read_mac=lambda: bytes.fromhex("020000000010"),
            get_secure_boot_enabled=lambda: 0,
            get_flash_encryption_enabled=lambda: False,
            flash_id=lambda: core.FLASH_ID, flash_set_parameters=Mock(),
            _port=types.SimpleNamespace(close=Mock()),
        )
        chip.run_stub = lambda: chip
        fake_tool = types.ModuleType("esptool")
        fake_tool.detect_chip = lambda *a, **kw: chip
        fake_cmds = types.ModuleType("esptool.cmds")
        fake_cmds.attach_flash = Mock()
        with patch.object(core, "version", return_value="5.4.0"), patch.dict(sys.modules, {
            "esptool": fake_tool, "esptool.cmds": fake_cmds,
        }):
            self.assertIs(core.connect_target("/dev/ttyUSB0", "02:00:00:00:00:10"), chip)
        chip.flash_set_parameters.assert_called_once_with(core.FLASH_SIZE)
        chip._port.close.assert_not_called()

    def test_security_features_rejected_before_stub_or_write(self):
        for secure_boot, encryption in ((True, False), (False, True), (None, False), (False, None)):
            with self.subTest(secure_boot=secure_boot, encryption=encryption):
                closed = []
                chip = types.SimpleNamespace(
                    CHIP_NAME="ESP32", read_mac=lambda: bytes.fromhex("020000000010"),
                    get_secure_boot_enabled=lambda: secure_boot,
                    get_flash_encryption_enabled=lambda: encryption,
                    run_stub=lambda: self.fail("Stub must not run on a protected/unknown target"),
                    _port=types.SimpleNamespace(close=lambda: closed.append(True)),
                )
                fake_tool = types.ModuleType("esptool")
                fake_tool.detect_chip = lambda *a, **kw: chip
                fake_cmds = types.ModuleType("esptool.cmds")
                fake_cmds.attach_flash = lambda *a: self.fail("Flash must not attach on a protected target")
                with patch.object(core, "version", return_value="5.4.0"), patch.dict(sys.modules, {
                    "esptool": fake_tool, "esptool.cmds": fake_cmds,
                }):
                    with self.assertRaises(ValueError):
                        core.connect_target("/dev/ttyUSB0", "02:00:00:00:00:10")
                self.assertEqual(closed, [True])

    def test_usb_port_rejects_network_and_arbitrary_files(self):
        for value in ("socket://192.0.2.10:6638", "/tmp/device", "../ttyUSB0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                core.validate_port(value)
        for value in ("/dev/ttyUSB0", "/dev/serial/by-id/usb-Silicon_Labs_CP2102N-if00-port0", "COM3"):
            self.assertEqual(core.validate_port(value), value)

    def test_bounded_read_uses_one_packet_window_and_checks_digest(self):
        data = b"a" * 1024 + b"b" * 1024
        esp = FakeESP(data)
        self.assertEqual(core.read_flash_bounded(esp, 0, len(data)), data)
        self.assertEqual(esp.requests, [(0, 2048, 1024, 1)])
        self.assertEqual(esp.acks, [1024, 2048])
        self.assertEqual(esp._port.timeout, 3)

    def test_truncated_packet_and_bad_checksum_fail(self):
        for frames in ([b"short"], [b"a" * 1024, b"\x00" * 16]):
            esp = FakeESP(b"a" * 1024)
            with patch.object(esp, "check_command"):
                esp.frames = list(frames)
                with self.assertRaises(RuntimeError):
                    core.read_flash_bounded(esp, 0, 1024)
            self.assertEqual(esp._port.timeout, 3)

    def test_blank_blocks_are_device_verified_and_manifest_matches(self):
        data = b"a" * 4096 + b"\xff" * 4096
        esp = FakeESP(data)
        with tempfile.TemporaryDirectory() as folder, patch.object(core, "FLASH_SIZE", 8192), patch.object(core, "BLOCK_SIZE", 4096):
            target = Path(folder) / "snapshot.bin"
            manifest = core.create_snapshot(esp, target, "02:00:00:00:00:10")
            self.assertEqual(target.read_bytes(), data)
            self.assertEqual(len(esp.requests), 1)
            self.assertEqual(manifest["verified_blank_block_count"], 1)
            self.assertEqual(manifest["read_block_count"], 1)
            self.assertFalse(Path(str(target) + ".partial").exists())
            manifest_path = Path(str(target) + ".manifest.json")
            core.validate_snapshot(target, manifest_path, "02:00:00:00:00:10")
            with self.assertRaises(ValueError):
                core.validate_snapshot(target, manifest_path, "02:00:00:00:00:11")
            target.write_bytes(b"x" + data[1:])
            with self.assertRaises(ValueError):
                core.validate_snapshot(target, manifest_path, "02:00:00:00:00:10")

    def test_whole_device_mismatch_leaves_only_partial(self):
        esp = FakeESP(b"a" * 4096 + b"\xff" * 4096)
        original = esp.flash_md5sum
        esp.flash_md5sum = lambda offset, length: "0" * 32 if length == 8192 else original(offset, length)
        with tempfile.TemporaryDirectory() as folder, patch.object(core, "FLASH_SIZE", 8192), patch.object(core, "BLOCK_SIZE", 4096):
            target = Path(folder) / "snapshot.bin"
            with self.assertRaises(RuntimeError):
                core.create_snapshot(esp, target, "02:00:00:00:00:10")
            self.assertFalse(target.exists())
            self.assertFalse(Path(str(target) + ".manifest.json").exists())
            self.assertTrue(Path(str(target) + ".partial").exists())

    def test_untrusted_firmware_and_existing_outputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / core.CORE_NAME
            target.write_bytes(b"untrusted")
            with self.assertRaises(ValueError):
                core.validate_firmware(target)
            with self.assertRaises(ValueError):
                core.snapshot_paths(target)

    def test_snapshot_dry_run_never_opens_usb(self):
        with tempfile.TemporaryDirectory() as folder:
            argv = ["esp32_core.py", "--port", "/dev/ttyUSB0", "--expect-base-mac",
                    "02:00:00:00:00:10", "--confirm-model", "SLZB-06", "snapshot",
                    "--out", str(Path(folder) / "snapshot.bin")]
            with patch.object(sys, "argv", argv), patch.object(core, "connect_target", side_effect=AssertionError("USB opened")):
                core.main()

    def test_changed_device_refuses_write(self):
        fake_cmds = types.ModuleType("esptool.cmds")
        fake_cmds.write_flash = lambda *a, **kw: self.fail("Unexpected flash write")
        fake_cmds.verify_flash = lambda *a, **kw: None
        esp = FakeESP(b"changed")
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"esptool.cmds": fake_cmds}):
            with self.assertRaises(ValueError):
                core.program_verified(esp, b"image", {"device_md5": "0" * 32}, Path(folder) / "receipt.json")

    def test_write_verification_controls_receipt_and_reset(self):
        for post_write_valid in (True, False):
            with self.subTest(post_write_valid=post_write_valid):
                image = b"known image"
                backup_digest = "1" * 32
                image_digest = hashlib.md5(image).hexdigest() if post_write_valid else "0" * 32
                chip = types.SimpleNamespace(
                    flash_md5sum=Mock(side_effect=[backup_digest, image_digest]),
                    hard_reset=Mock(),
                )
                fake_cmds = types.ModuleType("esptool.cmds")
                fake_cmds.write_flash = Mock()
                fake_cmds.verify_flash = Mock()
                manifest = {"device_md5": backup_digest, "sha256": "2" * 64,
                            "base_mac": "02:00:00:00:00:10"}
                with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"esptool.cmds": fake_cmds}):
                    receipt = Path(folder) / "receipt.json"
                    if post_write_valid:
                        core.program_verified(chip, image, manifest, receipt)
                        self.assertTrue(json.loads(receipt.read_text())["verified"])
                        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
                        chip.hard_reset.assert_called_once()
                    else:
                        with self.assertRaises(RuntimeError):
                            core.program_verified(chip, image, manifest, receipt)
                        self.assertFalse(receipt.exists())
                        chip.hard_reset.assert_not_called()
                    fake_cmds.write_flash.assert_called_once_with(
                        chip, [(0, image)], flash_freq="keep", flash_mode="keep",
                        flash_size="keep", erase_all=False, force=False)
                    fake_cmds.verify_flash.assert_called_once()


if __name__ == "__main__":
    unittest.main()
