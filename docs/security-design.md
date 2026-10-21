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

## Verified HTTPS/WSS host profiles

The attended Python tools share `scripts/tls_policy.py`. It uses platform CA
trust, required certificate and hostname checks, TLS 1.2 or later and OpenSSL
security level 2 or the stronger platform default. CPython 3.12 or later with a
maintained OpenSSL is the supported host. No helper disables verification.
The coordinator blocks redirects and ambient proxies; HA blocks HTTP and
WebSocket redirects and ambient proxies. The WebSocket handshake rejects the
first redirect before requesting its target, including same-origin redirects
and HTTPS-to-HTTP downgrades. Configure the direct Home Assistant base URL.
Firmware download redirects retain HTTPS certificate checks.

The ZHA helper sends its WebSocket authentication frame only after an
`auth_required` challenge. The complete authentication exchange has a 30-second
deadline; RPC deadlines cover both sending and receiving. A timed-out command
may already have been accepted by Home Assistant, so the helper never retries
it automatically. Inspect integration state before making another attempt.

For the complete strong-key host profile set:

```sh
export SLZB_TLS_SECURITY_LEVEL=3
```

The setting reaches the actual firmware `urllib` downloader, coordinator
`urllib` opener and HA `aiohttp` connector for both HTTPS and WSS. Level 3
requires at least 128-bit estimated strength (RSA/DH 3072 or EC 256), rejecting
marginal 2047-bit RSA keys that level 2 can accept after rounding. It may reject
otherwise valid legacy RSA-2048 peers. Provision compatible HTTPS peers before
selecting this profile; do not lower certificate verification to work around a
failure. Only values `2` and `3` are accepted, and neither can lower a stronger
platform default. OpenSSL implements crypto and secure handshake randomness.

Run the local check with the same environment and interpreter used for recovery:

```sh
PYTHONPATH=scripts .venv/bin/python -c 'from tls_policy import client_context
c = client_context()
print(c.security_level, c.minimum_version.name, c.verify_mode.name, c.check_hostname)'
```

`tests/test_strict_tls.py` drives all three actual clients against synthetic
HTTPS peers, using TLS 1.2 and 1.3. RSA-3072 chains succeed. A 2047-bit key in the
leaf, intermediate or root fails before HTTP requests, HA tokens or firmware
files are sent/written. Separate tests retain CA/hostname checks and prevent
lowering stronger platform policy. Certificates, tokens and payloads are invented;
no live coordinator, HA account or firmware is involved.

The firmware downloader additionally verifies recorded SHA-256 digests for both
the archive and extracted image. These pin the documented upstream bytes, not
the newest firmware or hardware suitability. Obtain source releases and firmware
through the documented HTTPS URLs; never trust a hash delivered over plaintext
as independent authentication.

## Legacy recovery and remaining limits

The original coordinator supports plaintext HTTP and serial-over-TCP recovery.
These are deliberately attended operations on an isolated trusted network, not
confidential or authenticated Internet protocols. Use HTTPS for the HA token
connection. The strong TLS option does not upgrade HTTP, serial bridges, USB
flashing or other upstream tools. Backup files contain network secrets and use
exclusive creation with private permissions. Keep them outside Git and restrict
access to the host and backup storage.

Do not expose recovery endpoints or run against an unverified target. Validate
hardware identity, exact image hash, flash layout and complete backups before
explicit writes. Synthetic tests and source-release signatures do not establish
safe hardware flashing. Upstream flashing tools and firmware have their own
provenance and security boundaries. No external-user password database is
implemented by these helpers.

Report issues through [SECURITY.md](../SECURITY.md). The OpenSSF self-assessment
records evidence and limitations; it is not a guarantee that a deployment is safe.

## Release-client transport

The shared release client delegates API requests to GitHub CLI. Apply the
[verified release TLS profile](release-tls-profile.md) when using its commands;
it preserves normal certificate checks and supports rejecting smaller keys.
This release-client profile is separate from the Python firmware, coordinator
and Home Assistant clients described above. It does not upgrade plaintext
legacy recovery protocols.
