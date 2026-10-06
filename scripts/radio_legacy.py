#!/usr/bin/env python3
"""Conservative wrapper around smlight-cc-flasher 0.1.7 for core 0.9.9."""
import argparse
import asyncio
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import sys

from fetch_firmware import HEX_SHA256
from slzb import request, status, validate_identity


def find_network_backup(value):
    """Accept one explicit backup; reject containers with ambiguous candidates."""
    if isinstance(value, dict):
        network = value.get("network_info")
        if (isinstance(network, dict) and isinstance(value.get("node_info"), dict)
                and value["node_info"].get("ieee")
                and isinstance(network.get("network_key"), dict)
                and network["network_key"].get("key")
                and all(key in network for key in ("channel", "pan_id", "extended_pan_id"))):
            return value
        if "backup" in value:
            # ha_zha.py explicitly selects the fresh complete backup here.
            return find_network_backup(value["backup"])
        found_items = []
        for item in value.values():
            found = find_network_backup(item)
            if found:
                found_items.append(found)
    elif isinstance(value, list):
        found_items = []
        for item in value:
            found = find_network_backup(item)
            if found:
                found_items.append(found)
    else:
        return None
    if len(found_items) > 1:
        raise ValueError("Ambiguous backup container: export one explicitly selected complete backup")
    return found_items[0] if found_items else None


def validate_inputs(args):
    if not re.fullmatch(r"[A-Za-z0-9.-]+", args.host):
        raise ValueError("Use an IPv4 address or DNS hostname, without a scheme or port")
    if not 1 <= args.port <= 65535:
        raise ValueError("Invalid TCP port")
    if hashlib.sha256(args.firmware.read_bytes()).hexdigest() != HEX_SHA256:
        raise ValueError("Only the recorded 20240710 OTHER coordinator image is accepted")
    if not find_network_backup(json.loads(args.network_backup.read_text())):
        raise ValueError("No recognizable zigpy network backup; do not erase the radio")


def patch_flasher(expected_host, expected_mac):
    import smlight_cc_flasher.command as commands
    import smlight_cc_flasher.cli as cli

    commands.MAX_BLOCK_SIZE = 128
    cli.MAX_BLOCK_SIZE = 128
    original_ack = commands.CommandInterface._wait_for_ack
    original_write = commands.CommandInterface._write

    async def wait_for_ack(self, command, timeout=10):
        return await original_ack(self, command, timeout=max(10, timeout))

    async def paced_write(self, data):
        await original_write(self, data)
        await asyncio.sleep(0.01)

    async def legacy_bootloader(self, host):
        if host != expected_host:
            raise ValueError("Unexpected bootloader target")
        base = f"http://{host}"
        state = await asyncio.to_thread(status, base)
        validate_identity(state, expected_mac)
        _, result = await asyncio.to_thread(request, base, "/api?action=8&cmd=2")
        if result.strip() != b"ok":
            raise RuntimeError("Legacy bootloader command was not accepted")
        return True

    commands.CommandInterface._wait_for_ack = wait_for_ack
    commands.CommandInterface._write = paced_write
    commands.Bootloader.invoke_smlight_net = legacy_bootloader
    return cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=6638)
    parser.add_argument("--expect-mac", required=True)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--network-backup", type=Path, required=True)
    parser.add_argument("--coordinator-stopped", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    validate_inputs(args)
    if not args.execute:
        print("Dry run: verified image and recognizable backup. Would erase/write/CRC-verify CC2652P via legacy Ethernet. No network request made.")
        return
    if not args.coordinator_stopped:
        raise ValueError("Stop/disable ZHA or Zigbee2MQTT, then pass --coordinator-stopped")
    if version("smlight-cc-flasher") != "0.1.7":
        raise ValueError("This adapter is validated only with smlight-cc-flasher 0.1.7")
    state = status(f"http://{args.host}")
    validate_identity(state, args.expect_mac)
    if state.get("operationalMode") != "Zigbee-to-Ethernet":
        raise ValueError("Coordinator must be in Zigbee-to-Ethernet mode")
    if state.get("connectedSocketStatus") != "No":
        raise ValueError("A serial client is connected; disconnect it before flashing")
    cli = patch_flasher(args.host, args.expect_mac)
    sys.argv = ["smlight_cc_flasher", "--host", args.host, "--port", str(args.port),
                "--baud", "115200", "--bootloader-reset", "network",
                "--erase", "--write", "--verify", str(args.firmware)]
    asyncio.run(cli.main())
    print("Flasher returned successfully. Restore/reconnect HA, then verify live firmware, network identity, and device reads.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
