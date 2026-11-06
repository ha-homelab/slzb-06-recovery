"""Preserve real distribution input checks on documentation-only pull requests."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import package_source


class DocumentationSourceInventoryTests(unittest.TestCase):
    def test_all_declared_distribution_inputs_are_present_and_regular(self):
        self.assertEqual(
            set(package_source.sources(ROOT)), set(package_source.inventory(ROOT))
        )


if __name__ == "__main__":
    unittest.main()
