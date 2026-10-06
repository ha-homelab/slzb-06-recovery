# Recovery case study — 2026-10-06

This record removes household addresses, device identities, secrets, raw logs,
and private deployment details. It distinguishes observations from inference.

## Starting point

After a household power outage, Home Assistant's Zigbee and some Matter devices
were reported unavailable. The Zigbee adapter was an original SMLIGHT SLZB-06,
with ESP32-D0WDQ5 reporting 16 MiB physical flash, core `0.9.9` (March 3, 2023),
and a CC2652P running Z-Stack `20230507`.

PoE powered the unit, but the initially isolated switch and then a bad uplink
cable prevented useful LAN access. After reconnecting/replacing the cable,
Ethernet and HTTP recovered. Reloading ZHA restored its serial connection.
Uncached reads to three paired mains-powered devices still failed with
`NWK_NO_ROUTE`. Cached availability had overstated actual radio health.

Multiple USB cable/adapter attempts never produced a USB device on the Mac,
including USB-C-to-C while powered by PoE. Neither a full ESP32 flash read nor
a supported USB core migration was therefore available during this session.

## Backups obtained

- Six core configuration JSON files plus status/checksums.
- Home Assistant ZHA configuration entry and a consistent `zigbee.db` snapshot.
- Zigpy network backups and current network settings, preserving identity,
  keys, counters, and device mappings.

The network data contained device information under `network_info`; counting
only a missing top-level `devices` property would have incorrectly called it
empty. These backup artifacts remain private and are not included here.

## Core upgrade outcome

Official `2.5.2` and `2.0.14` OTA images were uploaded in separate attempts.
Both returned HTTP 200 with `FAIL`, and the core restarted on `0.9.9`.
Both images were larger than the application slots in the downloaded legacy
full-image partition table. The actual installed partition table was not read,
so the slot mismatch remains a strongly supported explanation rather than a
captured updater diagnostic.

No full image was posted to the OTA endpoint; no custom partition migrator or
TFTP recovery was attempted. The ESP32 core remained `0.9.9`.

## Radio upgrade outcome

The official `20240710` **OTHER coordinator** image was programmed over wired
Ethernet using `smlight-cc-flasher 0.1.7`, with the legacy bootloader API adapted.
The default 252-byte transfer failed on the first data command after erase.
Reducing blocks to 128 bytes progressed to roughly 24%, then hit a one-second
acknowledgement timeout. After adding a minimum
ten-second acknowledgement timeout and ten-millisecond write pacing, programming
completed in approximately six minutes.

Both firmware segments passed the flasher's CRC verification:

```text
0x00000..0x2bf38  CRC32 0x5884637b
0x57fa8..0x58000  CRC32 0xed398d6d
```

This establishes a completed, verified radio write. Post-reconnect validation
is recorded separately below; it must not be inferred solely from the progress
bar or these checksums.

## Post-reconnect validation

ZHA eventually reached `loaded`; fresh network settings identified the running
radio as **Z-Stack 20240710**. Initialization took longer than the first 90-second
request timeout, while protocol diagnostics showed ongoing radio responses.
A timed-out request had not meant that HA had stopped initializing.

A newly created ZHA backup reported `is_complete: true`. Comparison against
the pre-flash network confirmed:

- The same coordinator IEEE, channel, PAN ID, extended PAN ID, and network update ID.
- Preserved network and trust-center key material.
- A network transmit counter that had not decreased.
- Thirteen key-table entries and thirteen network-address mappings.
- Fourteen ZHA records, including the coordinator, retained without re-pairing.

However, **all three uncached Basic manufacturer reads to paired mains-powered
devices still failed**. HA logs confirmed `NWK_NO_ROUTE` (205) for each. Thus the
radio flash and recovery of the same network were verified, but live Zigbee
device communication remained unresolved. No channel change or re-pairing was
performed. Antenna, location, powered routers, and mesh reachability remain
separate troubleshooting work; firmware success must not be presented as a
complete recovery of the household's devices.

## Limits and remaining options

- Radio firmware and ESP32 core have independent upgrade paths.
- A network firmware write is viable on this old core with a carefully adapted
  transport, but has erase/interruption risk and needs backups.
- A full core migration still needs a supported data/bootloader path or a
  separately engineered and validated migration mechanism.
- A fresh live response from real devices is the recovery criterion. Firmware
  version and integration status alone are insufficient.
- Matter health is tracked independently; this radio write does not establish
  any change to Matter devices.
