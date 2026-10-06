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
    for label, backup in (("before", before), ("after", after)):
        network = backup["network_info"]
        for field in ("channel", "pan_id", "extended_pan_id"):
            if network.get(field) is None:
                raise ValueError(f"{label}: missing required network field {field}")
        for field in ("network_key", "tc_link_key"):
            key = network.get(field)
            if not isinstance(key, dict) or not key.get("key") or key.get("seq") is None:
                raise ValueError(f"{label}: missing required key/sequence fields in {field}")
            for counter in ("tx_counter", "rx_counter"):
                if type(key.get(counter)) is not int or key[counter] < 0:
                    raise ValueError(f"{label}: missing or invalid {field}.{counter}")
    result = {key: old.get(key) == new.get(key) for key in ("channel", "pan_id", "extended_pan_id")}
    result["coordinator_ieee"] = before["node_info"].get("ieee") == after["node_info"].get("ieee")
    for field in ("network_key", "tc_link_key"):
        a, b = old.get(field), new.get(field)
        result[field] = a["key"] == b["key"]
        result[field + "_sequence"] = a["seq"] == b["seq"]
        for counter in ("tx_counter", "rx_counter"):
            result[f"{field}_{counter}_not_decreased"] = b[counter] >= a[counter]
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
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
