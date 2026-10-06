#!/usr/bin/env python3
"""Read/backup a legacy SLZB-06, or explicitly upload an app-only OTA image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request


CONFIG_FILES = tuple(f"{name}.json" for name in (
    "configEther", "configGeneral", "configSecurity", "configSerial", "configWifi", "system"
))


def private_write(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
        stream.write(data)


def validate_base_url(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise ValueError("Use an http(s) base URL without credentials, path, query, or fragment")
    return value.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected HTTP redirect; check the target address")


def request(base_url, path, *, data=None, content_type=None, timeout=20):
    headers = {"Accept-Encoding": "identity"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(validate_base_url(base_url) + path, data=data, headers=headers)
    # Do not send local coordinator requests through ambient proxy settings.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=timeout) as response:
        return response.headers, response.read()


def status(base_url):
    headers, _ = request(base_url, "/api?action=0&page=0")
    value = headers.get("respValuesArr")
    if not value:
        raise ValueError("No legacy status header; target is not the expected legacy API")
    state = json.loads(value)
    if not isinstance(state, dict):
        raise ValueError("Invalid status object")
    return state


def validate_identity(state, expected_mac):
    if state.get("hwRev") != "SLZB-06":
        raise ValueError("This helper supports only the original SLZB-06")
    if not re.match(r"^0\.9\.9(?:\s|$)", state.get("VERSION", "")):
        raise ValueError("This helper's API is only validated on core 0.9.9")
    if not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", expected_mac):
        raise ValueError("Expected MAC must have six colon-separated bytes")
    if state.get("ethMac", "").lower() != expected_mac.lower():
        raise ValueError("Ethernet MAC does not match the operator-supplied identity")


def check_ota(path, expected_sha, slot_size):
    path = Path(path)
    if not path.name.endswith("-ota.bin"):
        raise ValueError("Only an explicitly named -ota.bin app image is accepted")
    payload = path.read_bytes()
    if not payload or payload[0] != 0xE9:
        raise ValueError("Not an ESP application image")
    if hashlib.sha256(payload).hexdigest() != expected_sha.lower():
        raise ValueError("SHA-256 mismatch")
    if slot_size <= 0 or len(payload) > slot_size:
        raise ValueError("Image exceeds the supplied, independently verified OTA slot size")
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    backup = sub.add_parser("backup-core")
    backup.add_argument("--expect-mac", required=True)
    backup.add_argument("--out", type=Path, required=True)
    ota = sub.add_parser("ota-core")
    ota.add_argument("--expect-mac", required=True)
    ota.add_argument("--image", type=Path, required=True)
    ota.add_argument("--sha256", required=True)
    ota.add_argument("--slot-size", type=lambda x: int(x, 0), required=True)
    ota.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "ota-core":
        payload = check_ota(args.image, args.sha256, args.slot_size)
        if not args.execute:
            print(f"Dry run: app image {len(payload)} bytes fits supplied slot. No network request made.")
            return
    state = status(args.url)
    if args.action == "status":
        safe = ("hwRev", "VERSION", "espModel", "espFlashSize", "operationalMode",
                "ethConnection", "ethSpd", "uptime", "connectedSocketStatus")
        print(json.dumps({key: state.get(key) for key in safe}, indent=2))
        return
    validate_identity(state, args.expect_mac)
    if args.action == "backup-core":
        args.out.mkdir(mode=0o700, parents=False, exist_ok=False)
        manifest = {}
        for name in CONFIG_FILES:
            _, data = request(args.url, "/api?action=5&filename=" + urllib.parse.quote(name))
            if not isinstance(json.loads(data), dict):
                raise ValueError(f"Unexpected JSON object for {name}; backup is incomplete")
            private_write(args.out / name, data)
            manifest[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        private_write(args.out / "status.json", json.dumps(state, indent=2).encode())
        private_write(args.out / "manifest.json", json.dumps(manifest, indent=2).encode())
        print("Saved six private core configuration files and a checksum manifest. Keep this directory private.")
        return
    boundary = "slzb_" + os.urandom(16).hex()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"update\"; filename=\"firmware-ota.bin\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode()
    body += payload + f"\r\n--{boundary}--\r\n".encode()
    _, result = request(args.url, "/update", data=body,
                        content_type=f"multipart/form-data; boundary={boundary}", timeout=180)
    if result.strip() != b"OK":
        raise RuntimeError("OTA did not report OK. Do not assume it changed firmware; inspect after reboot.")
    print("Upload reported OK. Reconnect after reboot and independently verify the running version.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
