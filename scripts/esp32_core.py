#!/usr/bin/env python3
"""Guarded original SLZB-06 USB snapshot and exact core-2.5.2 programming.

Device qualification and observed hardware results are documented in
docs/usb-core-upgrade.md. Both commands are offline dry runs by default.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import struct
import time

from slzb import private_write

FLASH_SIZE = 16 * 1024 * 1024
FLASH_ID = 0x1840EF
BLOCK_SIZE = 256 * 1024
PACKET_SIZE = 1024
BAUD = 115200
CORE_NAME = "slzb-06-v2.5.2-full.bin"
CORE_SIZE = 2004768
CORE_SHA256 = "f3fd6a6a8c59c257a18fe398f4d0748729b5df3349db8d4557e50f47a1f903c9"


def normalize_mac(value):
    if not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", value):
        raise ValueError("Expected ESP32 base MAC must contain six colon-separated bytes")
    return value.lower()


def validate_port(value):
    if not re.fullmatch(r"(?:/dev/(?:ttyUSB\d+|ttyACM\d+|(?:cu|tty)\.(?:usbserial|usbmodem|SLAB_USBtoUART)[A-Za-z0-9._-]*|serial/by-id/[A-Za-z0-9._:+-]+)|COM[1-9]\d*)", value):
        raise ValueError("Use an explicit local USB serial device, not a network URL or arbitrary file")
    return value


def unused_path(path):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise ValueError("Output already exists; refusing to overwrite")
    if not path.parent.is_dir():
        raise ValueError("Create the private output directory first")


def snapshot_paths(output):
    output = Path(output)
    partial = Path(str(output) + ".partial")
    manifest = Path(str(output) + ".manifest.json")
    for path in (output, partial, manifest):
        unused_path(path)
    return output, partial, manifest


def read_flash_bounded(esp, offset, length, progress=None):
    """Use the stock stub READ_FLASH protocol with one 1 KiB packet in flight."""
    esp.check_command("read flash", esp.ESP_CMDS["READ_FLASH"],
                      struct.pack("<IIII", offset, length, PACKET_SIZE, 1))
    data = bytearray()
    old_timeout = esp._port.timeout
    esp._port.timeout = 10
    try:
        while len(data) < length:
            packet = esp.read()
            expected = min(PACKET_SIZE, length - len(data))
            if len(packet) != expected:
                raise RuntimeError("Unexpected flash-read packet length; snapshot is incomplete")
            data.extend(packet)
            esp.write(struct.pack("<I", len(data)))
            if progress:
                progress(offset + len(data))
        digest = esp.read()
        if len(digest) != 16 or hashlib.md5(data).digest() != digest:
            raise RuntimeError("Flash-read protocol checksum mismatch")
        return bytes(data)
    finally:
        esp._port.timeout = old_timeout


def create_snapshot(esp, output, expected_mac):
    output, partial, manifest_path = snapshot_paths(output)
    blank = b"\xff" * BLOCK_SIZE
    blank_md5 = hashlib.md5(blank).hexdigest()
    whole_md5, whole_sha = hashlib.md5(), hashlib.sha256()
    read_blocks = blank_blocks = 0
    last_progress = 0.0

    def progress(position):
        nonlocal last_progress
        now = time.monotonic()
        if now - last_progress > 15:
            print(f"Reading byte {position} / {FLASH_SIZE}", flush=True)
            last_progress = now

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(partial, flags, 0o600), "wb") as stream:
        for offset in range(0, FLASH_SIZE, BLOCK_SIZE):
            device_md5 = esp.flash_md5sum(offset, BLOCK_SIZE).lower()
            if device_md5 == blank_md5:
                data = blank
                blank_blocks += 1
            else:
                data = read_flash_bounded(esp, offset, BLOCK_SIZE, progress)
                read_blocks += 1
            if len(data) != BLOCK_SIZE or hashlib.md5(data).hexdigest() != device_md5:
                raise RuntimeError("Flash-block verification failed; snapshot is incomplete")
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            whole_md5.update(data)
            whole_sha.update(data)
            print(f"Verified {offset + BLOCK_SIZE} / {FLASH_SIZE} bytes", flush=True)

    device_md5 = esp.flash_md5sum(0, FLASH_SIZE).lower()
    if device_md5 != whole_md5.hexdigest():
        raise RuntimeError("Whole-device checksum mismatch; snapshot is incomplete")
    manifest = {
        "schema_version": 1, "verified": True, "board_model": "SLZB-06",
        "esp_chip": "ESP32", "base_mac": normalize_mac(expected_mac),
        "flash_jedec_id": FLASH_ID, "size": FLASH_SIZE,
        "sha256": whole_sha.hexdigest(), "snapshot_md5": whole_md5.hexdigest(),
        "device_md5": device_md5, "esptool_version": "5.4.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_block_count": read_blocks, "verified_blank_block_count": blank_blocks,
        "block_size": BLOCK_SIZE, "baud": BAUD, "packet_size": PACKET_SIZE,
        "max_in_flight_packets": 1,
    }
    # A hard link fails if output appeared meanwhile; rename could overwrite it.
    os.link(partial, output)
    private_write(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode())
    partial.unlink()
    print("Complete snapshot and private manifest verified. Target remains in download mode.")
    return manifest


def validate_snapshot(snapshot, manifest_path, expected_mac):
    data = Path(snapshot).read_bytes()
    manifest = json.loads(Path(manifest_path).read_text())
    if not isinstance(manifest, dict):
        raise ValueError("Invalid snapshot manifest")
    required = {"schema_version": 1, "verified": True, "board_model": "SLZB-06",
                "esp_chip": "ESP32", "base_mac": normalize_mac(expected_mac),
                "flash_jedec_id": FLASH_ID, "size": FLASH_SIZE,
                "esptool_version": "5.4.0"}
    if any(manifest.get(key) != value for key, value in required.items()):
        raise ValueError("Snapshot identity/verification manifest does not match this target")
    if len(data) != FLASH_SIZE or hashlib.sha256(data).hexdigest() != manifest.get("sha256"):
        raise ValueError("Snapshot size or SHA-256 mismatch")
    digest = hashlib.md5(data).hexdigest()
    if digest != manifest.get("snapshot_md5") or digest != manifest.get("device_md5"):
        raise ValueError("Snapshot does not match its recorded whole-device MD5")
    return manifest


def validate_firmware(path):
    path = Path(path)
    data = path.read_bytes()
    if (path.name != CORE_NAME or len(data) != CORE_SIZE
            or hashlib.sha256(data).hexdigest() != CORE_SHA256):
        raise ValueError("Only the exact recorded original SLZB-06 core-2.5.2 full image is accepted")
    return data


def connect_target(port, expected_mac):
    if version("esptool") != "5.4.0":
        raise ValueError("This helper requires esptool 5.4.0")
    import esptool
    from esptool.cmds import attach_flash

    esp = esptool.detect_chip(port, baud=BAUD)
    try:
        mac = ":".join(f"{item:02x}" for item in esp.read_mac())
        if esp.CHIP_NAME != "ESP32" or normalize_mac(mac) != normalize_mac(expected_mac):
            raise ValueError("Unexpected ESP32 chip or base MAC; no flash write performed")
        security_states = (esp.get_secure_boot_enabled(), esp.get_flash_encryption_enabled())
        # ESP32's secure-boot accessor can return integer 0, not only False.
        if any(type(state) not in (bool, int) or state != 0 for state in security_states):
            raise ValueError("Secure boot or flash encryption is enabled/unknown; this migration is unsupported")
        esp = esp.run_stub()
        attach_flash(esp)
        if esp.flash_id() & 0xFFFFFF != FLASH_ID:
            raise ValueError("Unexpected flash identity/capacity; only the recorded 16 MiB part is supported")
        esp.flash_set_parameters(FLASH_SIZE)
        return esp
    except BaseException:
        esp._port.close()
        raise


def program_verified(esp, image, manifest, receipt_path):
    """Write only after the connected device still matches the complete backup."""
    from esptool.cmds import verify_flash, write_flash

    unused_path(receipt_path)
    if esp.flash_md5sum(0, FLASH_SIZE).lower() != manifest["device_md5"]:
        raise ValueError("Device changed since its snapshot; make and verify a fresh complete backup")
    write_flash(esp, [(0, image)], flash_freq="keep", flash_mode="keep", flash_size="keep",
                erase_all=False, force=False)
    verify_flash(esp, [(0, image)], flash_freq="keep", flash_mode="keep", flash_size="keep", diff=False)
    if esp.flash_md5sum(0, len(image)).lower() != hashlib.md5(image).hexdigest():
        raise RuntimeError("Post-write firmware checksum mismatch; do not assume successful programming")
    receipt = {"verified": True, "firmware": CORE_NAME, "firmware_sha256": CORE_SHA256,
               "written_offset": 0, "written_size": len(image),
               "backup_sha256": manifest["sha256"], "base_mac": manifest["base_mac"],
               "verified_at": datetime.now(timezone.utc).isoformat()}
    private_write(receipt_path, (json.dumps(receipt, indent=2) + "\n").encode())
    esp.hard_reset()
    print("Firmware bytes verified and reset requested. Independently check boot, core version, settings, and Zigbee.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Explicit USB serial port; never auto-selected")
    parser.add_argument("--expect-base-mac", required=True, help="ESP32 base MAC, not Ethernet MAC")
    parser.add_argument("--confirm-model", choices=["SLZB-06"], required=True,
                        help="Confirm the physical label is the original model, not M/P7/P10/U")
    parser.add_argument("--controller-stopped", action="store_true")
    parser.add_argument("--execute", action="store_true")
    sub = parser.add_subparsers(dest="action", required=True)
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--out", type=Path, required=True)
    flash = sub.add_parser("flash-2.5.2")
    flash.add_argument("--firmware", type=Path, required=True)
    flash.add_argument("--snapshot", type=Path, required=True)
    flash.add_argument("--manifest", type=Path, required=True)
    flash.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    validate_port(args.port)
    expected_mac = normalize_mac(args.expect_base_mac)
    if args.action == "snapshot":
        snapshot_paths(args.out)
    else:
        image = validate_firmware(args.firmware)
        manifest = validate_snapshot(args.snapshot, args.manifest, expected_mac)
        unused_path(args.receipt)
    if not args.execute:
        print(f"Dry run: {args.action} inputs accepted. No USB access, reset, or flash write performed.")
        return
    if not args.controller_stopped:
        raise ValueError("Disable ZHA/Zigbee2MQTT before download mode, then pass --controller-stopped")
    esp = connect_target(args.port, expected_mac)
    try:
        if args.action == "snapshot":
            create_snapshot(esp, args.out, expected_mac)
        else:
            program_verified(esp, image, manifest, args.receipt)
    finally:
        esp._port.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
