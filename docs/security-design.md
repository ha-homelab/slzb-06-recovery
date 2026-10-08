# Security design and verification

## Scope and trust boundaries

The project provides attended backup, recovery and firmware helpers for the original SMLIGHT SLZB-06.

Coordinator backups contain Zigbee network secrets. Keep them outside Git and protect local copies. The legacy Ethernet path may use plaintext HTTP and serial-over-TCP; use a trusted isolated network. Verify the exact hardware, backup completeness, firmware digest and target before any write. Unit tests and command help never establish that a live device is safe to flash.

## Source and operating documentation

- [scripts/esp32_core.py](../scripts/esp32_core.py)
- [scripts/radio_legacy.py](../scripts/radio_legacy.py)
- [scripts/ha_zha.py](../scripts/ha_zha.py)
- [docs/upgrade-runbook.md](../docs/upgrade-runbook.md)

## Regression evidence

- [tests/test_safety.py](../tests/test_safety.py)
- [tests/test_esp32_core.py](../tests/test_esp32_core.py)
- [tests/test_ha_rpc.py](../tests/test_ha_rpc.py)

Run the documented commands in [CONTRIBUTING.md](../CONTRIBUTING.md) and the
[CI workflow](../.github/workflows/ci.yml). Preserve negative tests for rejected inputs,
unavailable dependencies, authorization failures and cancellation. A passing
test run describes its fixtures and environment; it does not certify every
upstream service, hardware model or production deployment.

## Firmware downloader HTTPS profile

`scripts/fetch_firmware.py` uses the standard-library HTTPS client, with normal
certificate and hostname verification. The supported download profile is
CPython 3.12 or newer with OpenSSL security level 2 or higher and a minimum of
TLS 1.2. Keep Python and OpenSSL updated. Alternative implementations, older
interpreters and vendor-modified TLS defaults are outside this verified profile.

Run this with the same interpreter that will run the downloader. It reports the
local defaults and exits unsuccessfully when the profile is not met:

```sh
python3 -c 'import platform, ssl, sys
context = ssl.create_default_context()
print(platform.python_implementation(), platform.python_version())
print(ssl.OPENSSL_VERSION)
print("security_level=", context.security_level,
      "minimum_tls=", context.minimum_version.name,
      "verify_mode=", context.verify_mode.name,
      "check_hostname=", context.check_hostname)
supported = (platform.python_implementation() == "CPython"
             and sys.version_info >= (3, 12)
             and context.security_level >= 2
             and context.minimum_version >= ssl.TLSVersion.TLSv1_2
             and context.verify_mode == ssl.CERT_REQUIRED
             and context.check_hostname)
raise SystemExit(0 if supported else 1)'
```

This checks the local runtime, not the identity of a remote host. Each HTTPS
connection still verifies its peer. On CPython 3.12.14/OpenSSL 3.5.8, local tests
of the actual downloader rejected RSA-1024 leaf, intermediate and root keys
before any HTTP request or file write, under both TLS 1.2 and TLS 1.3. A trusted
RSA-2048 chain downloaded and verified a synthetic ZIP/HEX pair. The test changed
only the download URL and expected hashes to local fixtures; it did not replace
the downloader's transport or lower its TLS policy. A separate client with a
deliberately lower policy verified that each synthetic chain was otherwise
usable. No device or real firmware was involved.

The downloader also verifies the independently recorded SHA-256 values for
both the archive and extracted image. Preserve those checks. This HTTPS profile
does not add encryption to the legacy device's HTTP or serial-over-TCP recovery
connections and does not establish the runtime policy of other host tools.

## Home Assistant and coordinator HTTPS/WSS profile

The same CPython 3.12+ / OpenSSL security-level-2 / TLS-1.2-minimum profile
applies when `scripts/slzb.py` receives an HTTPS coordinator URL and when
`scripts/ha_zha.py` connects to Home Assistant through HTTPS and WSS. Both retain
normal certificate and hostname verification. The coordinator helper uses
standard-library `urllib`; the Home Assistant helper uses the standard verified
`aiohttp` session. Neither helper lowers the TLS policy to accept a weak peer.

Install `requirements-ha.txt` with `--require-hashes` as shown in the README.
Run the [runtime check above](#firmware-downloader-https-profile) with
`.venv-ha/bin/python` in place of `python3`, and inspect the installed dependency:

```sh
.venv-ha/bin/python -c 'import aiohttp; print(aiohttp.__version__)'
```

The checked dependency lock currently selects `aiohttp 3.14.4`. Keep both the
lock and the interpreter updated. The verified runtime was CPython 3.12.14,
OpenSSL 3.5.8 and aiohttp 3.14.4. Tests called the unchanged coordinator
status/request and Home Assistant backup code against synthetic local servers:
RSA-1024 leaf, intermediate and root keys were rejected under TLS 1.2 and 1.3.
Coordinator and initial Home Assistant HTTPS failures occurred before HTTP or
authentication. A separate WSS test allowed the initial verified HTTPS response,
then offered the weak chain on the WebSocket connection; it was rejected before
WebSocket HTTP, token exchange or backup output. Strong RSA-2048 chains completed
the simulated status and backup flows; backup output retained mode `0600`.
A separate lower-policy client verified the test certificates' trust and
hostname validity. No actual coordinator, Home Assistant service or network
backup was used.

This profile only covers those HTTPS/WSS paths. An explicit HTTP URL remains
plaintext, including any Home Assistant token sent over it; use an isolated
trusted network for legacy recovery and HTTPS for Home Assistant whenever
available. The serial bridge and upstream flashing tools have separate trust
boundaries. A custom interpreter, TLS override or externally terminated proxy
requires its own assessment. The host profile does not prove deployed device
identity, firmware authenticity or safe hardware operations.

## Remaining security assessment

Review legacy plaintext device protocols and documented firmware provenance against the delivery and cryptographic criteria. Record static-analysis and warning disposition; hardware acceptance is separate.

Report new issues through [SECURITY.md](../SECURITY.md). An OpenSSF assessment
records evidence and applicability; it is not a guarantee that a system is safe.
