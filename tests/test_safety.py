import copy
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compare_network
import fetch_firmware
import radio_legacy
import slzb


def fixture():
    # Synthetic, not a real Zigbee backup or usable key.
    return {"node_info": {"ieee": "00:00:00:00:00:00:00:01"}, "network_info": {
        "channel": 20, "pan_id": "0001", "extended_pan_id": "example",
        "network_key": {"key": "synthetic-test-key", "seq": 0, "tx_counter": 100, "rx_counter": 0},
        "tc_link_key": {"key": "synthetic-tc-key", "seq": 0, "tx_counter": 0, "rx_counter": 0},
        "nwk_addresses": {"synthetic-router": 1}, "key_table": [],
    }}


class GuardTests(unittest.TestCase):
    def test_wrong_hardware_core_and_mac_are_rejected(self):
        good = {"hwRev": "SLZB-06", "VERSION": "0.9.9 (build)", "ethMac": "02:00:00:00:00:10"}
        slzb.validate_identity(good, good["ethMac"].lower())
        for key, value in (("hwRev", "SLZB-06M"), ("VERSION", "0.9.90"),
                           ("VERSION", "2.5.2"), ("ethMac", "02:00:00:00:00:11")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                slzb.validate_identity({**good, key: value}, good["ethMac"])

    def test_ota_rejects_full_images_oversize_and_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "firmware-ota.bin"
            payload = b"\xe9" + b"a" * 50
            path.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            self.assertEqual(slzb.check_ota(path, digest, 100), payload)
            with self.assertRaises(ValueError):
                slzb.check_ota(path, digest, 50)
            with self.assertRaises(ValueError):
                slzb.check_ota(path, "0" * 64, 100)
            full = path.with_name("firmware-full.bin")
            full.write_bytes(payload)
            with self.assertRaises(ValueError):
                slzb.check_ota(full, digest, 100)

    def test_private_write_is_exclusive_and_restrictive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret.json"
            slzb.private_write(path, b"private")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                slzb.private_write(path, b"replace")
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(FileExistsError):
                slzb.private_write(link, b"replace")
            self.assertEqual(path.read_bytes(), b"private")

    def test_url_rejects_credentials_path_and_redirect(self):
        self.assertEqual(slzb.validate_base_url("http://192.0.2.10/"), "http://192.0.2.10")
        for url in ("http://user:pass@example.test", "http://example.test/api", "file:///tmp/test", "http://example.test?token=x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                slzb.validate_base_url(url)
        with self.assertRaises(ValueError):
            slzb.NoRedirect().redirect_request(None, None, 302, "", {}, "http://other.test")

    def test_nested_backup_without_top_level_devices(self):
        backup = fixture()
        self.assertIs(radio_legacy.find_network_backup({"backup": backup}), backup)
        self.assertIsNone(radio_legacy.find_network_backup({"devices": []}))
        broken = fixture()
        broken["network_info"]["network_key"] = None
        self.assertIsNone(radio_legacy.find_network_backup(broken))

    def test_compare_detects_key_identity_and_counter_changes(self):
        before = fixture()
        after = copy.deepcopy(before)
        after["network_info"]["network_key"]["tx_counter"] += 100
        self.assertTrue(all(compare_network.compare(before, after).values()))
        after["network_info"]["network_key"]["key"] = "changed"
        after["network_info"]["network_key"]["tx_counter"] = 1
        after["node_info"]["ieee"] = "changed"
        result = compare_network.compare(before, after)
        self.assertFalse(result["network_key"])
        self.assertFalse(result["network_key_tx_counter_not_decreased"])
        self.assertFalse(result["coordinator_ieee"])

    def test_comparison_rejects_missing_key_or_counter_fields(self):
        before = fixture()
        for key, field in (("tc_link_key", "key"), ("network_key", "tx_counter"), ("tc_link_key", "rx_counter")):
            broken = copy.deepcopy(before)
            del broken["network_info"][key][field]
            with self.subTest(key=key, field=field), self.assertRaises(ValueError):
                compare_network.compare(before, broken)

    def test_ambiguous_backup_list_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            radio_legacy.find_network_backup([fixture(), fixture()])
        backup = fixture()
        self.assertIs(radio_legacy.find_network_backup({"backup": backup, "settings": fixture()}), backup)

    def test_download_rejects_unexpected_bytes(self):
        with self.assertRaises(ValueError):
            fetch_firmware.extract_verified(b"not the official archive")

    def test_radio_dry_run_does_not_contact_device(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "backup.json"
            backup.write_text(json.dumps({"backup": fixture()}))
            firmware = Path(directory) / "firmware.hex"
            firmware.write_bytes(b"test")
            args = ["radio_legacy.py", "--host", "192.0.2.10", "--expect-mac", "02:00:00:00:00:10",
                    "--firmware", str(firmware), "--network-backup", str(backup)]
            with patch.object(sys, "argv", args), patch.object(radio_legacy, "HEX_SHA256", hashlib.sha256(b"test").hexdigest()), \
                    patch.object(radio_legacy, "status", side_effect=AssertionError("network used")):
                radio_legacy.main()


if __name__ == "__main__":
    unittest.main()
