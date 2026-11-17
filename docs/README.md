# SLZB-06 recovery — documentation index

This index covers the attended backup, upgrade and recovery path for the original
SMLIGHT SLZB-06 (ESP32 + CC2652P): the ordered runbook, the two firmware targets,
and the field notes and evidence behind them. It does not apply unchanged to
SLZB-06M, P7 or P10.

## Get started

- [Complete upgrade and recovery runbook](upgrade-runbook.md): the ordered route
  through every stage below.
- [Update the ESP32 core from the browser](browser-core-update.md): the short path
  when USB access still works.
- [Device capabilities and other options](capabilities.md): transport, firmware
  variants and applicability.
- [Recovery case study — 2026-10-06](case-study.md): what failed and in what order.

## Back up before touching anything

- [Backups and restoring the same Zigbee network](backups.md): the ZHA network
  backup stage.
- [USB core snapshot and guarded 2.5.2 migration](usb-core-upgrade.md).
- [Synology VMM to a Linux guest: temporary USB ownership](synology-usb-passthrough.md).

## Update firmware

- [ESP32 core firmware: OTA, USB and partition limits](core-firmware.md).
- [Updating the CC2652P coordinator over Ethernet](radio-firmware.md).

## Troubleshoot

- [Troubleshooting by layer](troubleshooting.md): power, Ethernet, IP routing, the
  serial bridge, the radio and ZHA.
- [Verified HTTPS/WSS host profiles](security-design.md#verified-httpswss-host-profiles).

## Reference

- [Sources and evidence](sources.md): reviewed web documentation and upstream
  references.
- [Zigbee field guide illustrations](diagrams/README.md): original SVGs, editable
  HTML sources and regeneration steps.

## Development and release

- [Security design and verification](security-design.md).
- [Quality evidence and assessment limits](quality.md) and
  [OpenSSF evidence](openssf-evidence.md).
- [Release helper TLS profile](release-tls-profile.md).
- [Release-candidate fuzz testing](fuzzing.md) and [RC fuzzing](rc-fuzzing.md).

Shared repository policy (`release-workflow.md`, `quality.md`,
`openssf-evidence.md`, `runner-preflight.md`, `release-read-safety.md`,
`VERSIONING.md`) comes from the shared release toolkit and is summarized rather
than repeated here.

The case study and field notes are historical records of one recovery session.
They describe that hardware revision, not a live fleet or a supported vendor
procedure.
