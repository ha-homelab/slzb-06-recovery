# SLZB-06 recovery notes and tools

Practical recovery, backups, firmware upgrades, and troubleshooting for the
**original SMLIGHT SLZB-06: ESP32 + Texas Instruments CC2652P**. This is an
independent community project, not SMLIGHT support or firmware distribution.
It does **not** apply unchanged to SLZB-06M, P7, P10, or other variants.

There are two separate firmware targets:

- **ESP32 core** runs Ethernet, the web interface, and the serial bridge.
  Core `0.9.9` can serve HTTP and carry a Zigbee firmware update even when a
  modern core image will not fit its OTA partition.
- **CC2652P radio** runs the Zigbee coordinator and stores network state.
  Updating it over Ethernet does not upgrade the ESP32 core. Erasing it can
  require restoring the existing Zigbee network from a verified backup.

Our [case study](docs/case-study.md) records unsuccessful core OTA attempts,
a verified radio upgrade to Z-Stack `20240710`, and recovery of three live
device reads after repositioning/reconnection. A later USB migration captured
a verified full 16 MiB backup and successfully wrote and booted core `2.5.2`.
**Ethernet recovery and live Zigbee validation after that core migration are
still pending.** The earlier live successes must not be read as post-core
validation. Read the results and limitations before choosing a procedure.

## Start here

1. [Identify the device and isolate the fault](docs/troubleshooting.md).
2. [Back up the core, Home Assistant, and Zigbee network](docs/backups.md).
3. Choose [core firmware](docs/core-firmware.md) or
   [Zigbee radio firmware](docs/radio-firmware.md).
4. Verify the running firmware, network identity, and live device communication.

See [device capabilities and other options](docs/capabilities.md) for transport,
power, coordinator/router roles, and the limits of later Thread/Bluetooth options.

Use stable power and a **wired** host for radio flashing through the legacy
bridge. Disable ZHA/Zigbee2MQTT while a flasher owns the serial connection.
Keep the antenna attached. Do not reset the network, delete the integration,
or re-pair devices merely because the coordinator has become unavailable.

## Tools

Requires Python 3.12+ for the full workflow. The HTTP and firmware download
helpers use the standard library. Home Assistant access needs `requirements-ha.txt`;
the legacy radio wrapper needs `requirements-radio.txt` on a Linux host, and
the USB core helper needs `requirements-core.txt`. None of the commands below
flashes firmware.

```sh
python3 scripts/slzb.py --url http://192.0.2.10 status
python3 scripts/slzb.py --help
python3 scripts/radio_legacy.py --help
python3.12 -m venv .venv-ha
.venv-ha/bin/python -m pip install -r requirements-ha.txt
.venv-ha/bin/python -m unittest discover -s tests -v
```

`192.0.2.10`, `ha.example.test`, and example MAC addresses in this project are
documentation placeholders. Replace them with identities you have independently
checked. The status helper deliberately omits IP/MAC and Wi-Fi settings from its
output; backup files still contain sensitive data.

- `scripts/slzb.py`: legacy status, private configuration export, guarded
  app-only core OTA upload. OTA is a dry run without `--execute`; it also needs
  a checksum and an independently established slot size.
- `scripts/ha_zha.py`: fresh complete ZHA backup, deliberate disable/enable/reload,
  and an uncached Basic-cluster read. Lifecycle changes require `--execute`.
- `scripts/fetch_firmware.py`: download and hash-check the specific upstream
  CC2652P `20240710` image used in this case study.
- `scripts/radio_legacy.py`: adapt SMLIGHT's `0.1.7` flasher to the `0.9.9` API
  and small legacy bridge buffers. Dry run by default; only the tested image
  hash is accepted.
- `scripts/compare_network.py`: compare private before/after network identity
  and key data without printing secret values.
- `scripts/esp32_core.py`: [complete USB backup and exact core-2.5.2 migration](docs/usb-core-upgrade.md),
  with pinned esptool, chip/security checks, verified backup freshness, and
  explicit execution. See also the [temporary Synology VMM USB path](docs/synology-usb-passthrough.md).

These tools do not automatically recover from failed flashes, promise zero
downtime, or prove that a backup can be restored on every software version.
The guards reduce common mistakes but cannot verify physical hardware or power.

## Public repository boundary

Keep firmware downloads in ignored `artifacts/`, and backups/logs in ignored
`backups/` or `private/`. **Never commit Zigbee network backups, `zigbee.db`,
Home Assistant `.storage`, access tokens, Wi-Fi credentials, real household
addresses, raw diagnostics, or Terraform state.** `.gitignore` is only a guard;
inspect the staged diff before publishing anything.

Repository settings are managed by
[HA Homelab Terraform](https://github.com/4alvit/terraform-github-ha-homelab).
CI runs offline tests and syntax checks; it never talks to household hardware.

See [sources and evidence](docs/sources.md) for upstream documentation and
the distinction between observed behavior, source analysis, and hypotheses.

## License

[MIT](LICENSE) for original documentation and helpers. Firmware is downloaded
from its upstream project and remains under its own terms. The SMLIGHT flasher
is an external Apache-2.0 dependency; it is not vendored here.
