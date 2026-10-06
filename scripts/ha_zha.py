#!/usr/bin/env python3
"""Private ZHA backup, deliberate lifecycle controls, and uncached device reads."""
import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path

import aiohttp

from slzb import private_write, validate_base_url


async def rpc(ws, message, timeout=90):
    await ws.send_json(message)
    async with asyncio.timeout(timeout):
        while True:
            result = await ws.receive_json()
            if result.get("id") == message["id"]:
                if not result.get("success"):
                    code = result.get("error", {}).get("code", "unknown")
                    raise RuntimeError(f"HA rejected {message['type']} ({code})")
                return result["result"]


async def run(args):
    base = validate_base_url(args.url)
    token = os.environ.get("HA_TOKEN") or getpass.getpass("Home Assistant long-lived access token: ")
    if not token:
        raise ValueError("An access token is required")
    async with aiohttp.ClientSession(
        headers={"Authorization": "Bearer " + token},
        timeout=aiohttp.ClientTimeout(total=120), trust_env=False,
    ) as session:
        async with session.get(base + "/api/config/config_entries/entry", allow_redirects=False) as response:
            response.raise_for_status()
            entries = [entry for entry in await response.json() if entry.get("domain") == "zha"]
        if args.action == "status":
            print(json.dumps([{key: entry.get(key) for key in ("entry_id", "state", "disabled_by")} for entry in entries], indent=2))
            return
        if args.action in ("disable", "enable", "reload"):
            if args.entry_id not in {entry["entry_id"] for entry in entries}:
                raise ValueError("Entry ID is not a ZHA integration on this HA server")
            if not args.execute:
                print(f"Dry run: would {args.action} the selected ZHA integration; no change made.")
                return
            if args.action == "reload":
                async with session.post(base + f"/api/config/config_entries/entry/{args.entry_id}/reload", allow_redirects=False) as response:
                    response.raise_for_status()
                    result = await response.json()
                    if not result.get("require_restart") is False:
                        print("HA accepted reload; inspect integration state and any restart requirement.")
                    else:
                        print("HA reload request accepted.")
                return
        async with session.ws_connect(base + "/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                raise RuntimeError("Home Assistant authentication failed")
            if args.action in ("disable", "enable"):
                await rpc(ws, {"id": 1, "type": "config_entries/disable", "entry_id": args.entry_id,
                               "disabled_by": "user" if args.action == "disable" else None}, timeout=300)
                print(f"HA accepted {args.action}. Check actual integration state before proceeding.")
            elif args.action == "backup":
                created = await rpc(ws, {"id": 1, "type": "zha/network/backups/create"})
                if not created.get("is_complete") or not isinstance(created.get("backup"), dict):
                    raise RuntimeError("ZHA did not return a complete backup; do not erase the radio")
                settings = await rpc(ws, {"id": 2, "type": "zha/network/settings"})
                payload = {"backup": created["backup"], "settings": settings, "is_complete": True}
                private_write(args.out, json.dumps(payload, indent=2).encode())
                network = created["backup"].get("network_info", {})
                print(json.dumps({"saved": True, "is_complete": True,
                                  "backup_time": created["backup"].get("backup_time"),
                                  "known_addresses": len(network.get("nwk_addresses", {})),
                                  "key_table_entries": len(network.get("key_table", []))}, indent=2))
            elif args.action == "live-read":
                devices = await rpc(ws, {"id": 1, "type": "zha/devices"})
                device = next((item for item in devices if item.get("ieee") == args.ieee), None)
                if device is None:
                    raise ValueError("Device is not present in ZHA")
                endpoints = device.get("signature", {}).get("endpoints", {})
                endpoint = next((int(key) for key, value in endpoints.items()
                                 if "0x0000" in value.get("input_clusters", [])), None)
                if endpoint is None:
                    raise ValueError("Device has no Basic input cluster in its stored signature")
                await rpc(ws, {"id": 2, "type": "zha/devices/clusters/attributes/value", "ieee": args.ieee,
                               "endpoint_id": endpoint, "cluster_id": 0, "cluster_type": "in", "attribute": 4})
                print("Uncached Basic manufacturer attribute read completed. No actuator command was sent.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    backup = sub.add_parser("backup")
    backup.add_argument("--out", type=Path, required=True)
    live = sub.add_parser("live-read")
    live.add_argument("--ieee", required=True)
    for action in ("disable", "enable", "reload"):
        command = sub.add_parser(action)
        command.add_argument("--entry-id", required=True)
        command.add_argument("--execute", action="store_true")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    try:
        main()
    except asyncio.TimeoutError as exc:
        raise SystemExit("Request timed out. HA may still be initializing or applying the change. Run the status command and inspect HA logs before retrying or assuming failure.") from exc
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
