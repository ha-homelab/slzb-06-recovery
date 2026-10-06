#!/usr/bin/env python3
"""Compare private before/after zigpy backups without displaying network secrets."""
import argparse
import json
from pathlib import Path

from radio_legacy import find_network_backup


def compare(before, after):
    before, after = find_network_backup(before), find_network_backup(after)
    if before is None or after is None:
        raise ValueError("Both files must contain a recognizable zigpy network backup")
    old, new = before["network_info"], after["network_info"]
    result = {key: old.get(key) == new.get(key) for key in ("channel", "pan_id", "extended_pan_id")}
    result["coordinator_ieee"] = before["node_info"].get("ieee") == after["node_info"].get("ieee")
    for field in ("network_key", "tc_link_key"):
        a, b = old.get(field), new.get(field)
        if isinstance(a, dict) and isinstance(b, dict):
            result[field] = a.get("key") == b.get("key")
            if field == "network_key" and isinstance(a.get("tx_counter"), int) and isinstance(b.get("tx_counter"), int):
                result["tx_counter_not_decreased"] = b["tx_counter"] >= a["tx_counter"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    result = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()))
    print(json.dumps(result, indent=2))
    if not all(result.values()):
        raise SystemExit("Network identity comparison failed. Investigate before pairing or changing the network.")


if __name__ == "__main__":
    main()
