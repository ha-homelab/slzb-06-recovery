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

## Remaining security assessment

Review legacy plaintext device protocols and documented firmware provenance against the delivery and cryptographic criteria. Record static-analysis and warning disposition; hardware acceptance is separate.

Report new issues through [SECURITY.md](../SECURITY.md). An OpenSSF assessment
records evidence and applicability; it is not a guarantee that a system is safe.
