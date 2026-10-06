#!/usr/bin/env python3
"""Fetch the specific upstream CC2652P coordinator image used in the case study."""
import argparse
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

from slzb import private_write

NAME = "CC1352P2_CC2652P_other_coordinator_20240710"
URL = "https://github.com/Koenkk/Z-Stack-firmware/releases/download/Z-Stack_3.x.0_coordinator_20240710/" + NAME + ".zip"
ARCHIVE_SHA256 = "9622142c2e4d0d367148e6d54d4efa19be2877658328fdaa240a4df4655adbc0"
HEX_SHA256 = "1e81ad785ecb733e83ab556446d6ece6de0d4346216c7c9621cf2dc8fa26bea7"


def extract_verified(data):
    if hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Upstream archive does not match the recorded SHA-256")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        matches = [name for name in archive.namelist() if Path(name).name == NAME + ".hex"]
        if len(matches) != 1:
            raise ValueError("Archive has no unique expected HEX image")
        payload = archive.read(matches[0])
    if hashlib.sha256(payload).hexdigest() != HEX_SHA256:
        raise ValueError("HEX image hash mismatch")
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read(2_000_000)
    payload = extract_verified(data)
    args.out.mkdir(mode=0o700, exist_ok=True)
    private_write(args.out / (NAME + ".zip"), data)
    private_write(args.out / (NAME + ".hex"), payload)
    print("Saved verified upstream archive and HEX. This is the tested version, not a claim of latest firmware.")


if __name__ == "__main__":
    main()
