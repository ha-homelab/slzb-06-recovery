"""Regressions for malformed external status and nested backup data."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import radio_legacy
import slzb


class MalformedInputs(unittest.TestCase):
    def test_status_fields_reject_non_strings(self):
        good = {"hwRev": "SLZB-06", "VERSION": "0.9.9", "ethMac": "02:00:00:00:00:10"}
        for field in ("VERSION", "ethMac"):
            for value in (None, False, 42, [], {}):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    slzb.validate_identity({**good, field: value}, good["ethMac"])

    def test_deep_backup_containers_fail_with_a_validation_error(self):
        value = None
        for _ in range(1500):
            value = {"backup": value}
        with self.assertRaisesRegex(ValueError, "nesting"):
            radio_legacy.find_network_backup(value)

    def test_oversized_container_has_a_work_budget(self):
        with self.assertRaisesRegex(ValueError, "large"):
            radio_legacy.find_network_backup([None] * 10001)

    def test_cyclic_non_json_input_also_stops(self):
        value = {}
        value["backup"] = value
        with self.assertRaises(ValueError):
            radio_legacy.find_network_backup(value)
