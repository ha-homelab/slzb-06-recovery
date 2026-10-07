# Recovery case study — 2026-10-06

This record removes household addresses, device identities, secrets, raw logs,
and private deployment details. It distinguishes observations from inference.

**Outcomes by stage:** after the radio upgrade and coordinator repositioning/
reconnection, three live device checks passed without a channel change or
re-pairing. Later, a full USB backup and core `2.5.2` write/boot were verified.
Ethernet recovery and live Zigbee checks **after the core migration remain
pending**. The sequence below preserves those separate checkpoints and does
not isolate a single root cause.

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

Initial USB cable/adapter attempts produced no USB device on the Mac, including
USB-C-to-C while powered by PoE. Later, USB through a Synology host and Linux
guest provided a usable backup/migration path, described below.

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
full-image partition table. A later device-MD5-verified USB backup confirmed
the **actual installed** slots were also `0x140000` bytes: neither image fits.
The updater's internal error code was not captured.

No full image was posted to the OTA endpoint; no custom partition migrator or
TFTP recovery was attempted. At this stage, the ESP32 core remained `0.9.9`.

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
- Preserved network and trust-center key material and key sequences.
- Network and trust-center transmit/receive counters that had not decreased.
- Thirteen key-table entries and thirteen network-address mappings.
- Fourteen ZHA records, including the coordinator, retained without re-pairing.

The public comparison helper was also run locally against the private
before/after data: all twelve checks passed. No input backup data is published.

However, **all three uncached Basic manufacturer reads to paired mains-powered
devices still failed**. HA logs confirmed `NWK_NO_ROUTE` (205) for each. Thus the
radio flash and recovery of the same network were verified, but live Zigbee
device communication was still unresolved at this stage. A refreshed topology
scan showed no coordinator neighbors, unlike older cached topology records. No channel change
or re-pairing was performed. Antenna, location, powered routers, and mesh
reachability still needed separate checks; firmware success alone had not
established live device communication.

## Controlled follow-up radio checks

With ZHA disabled to give a standalone `zigpy-znp` client exclusive radio
ownership, the client started in `read_only` mode on the existing network.
Explicit `SYS.SetTxPower` requests for both **8 dBm and 20 dBm** were accepted
by the radio. At each setting, three ZDO network-address queries addressed by
the paired devices' IEEE identities timed out after 20 seconds. The coordinator's
`MgmtLqi` request returned `SUCCESS` with **zero neighbors** at both settings.
Acknowledged power settings are not measurements of radiated output power.

Power was restored to **8 dBm**. The HA country setting was `US`, with no explicit
transmit-power override; the installed zigpy default-selection logic chose
8 dBm. This describes that software configuration, not a universal setting or
recommendation. The probe validated the existing coordinator identity and
channel and used `read_only` startup. The earlier before/after firmware
comparison had already confirmed preserved keys and identity; no fresh
post-power-test key comparison was performed. The private probe and household
identifiers are not published.

Separately, one HA diagnostic energy scan reported channel 25 at approximately
**68% of the raw 0–255 energy scale**; the other channels ranged from roughly
16% to 97% of that scale. These normalized readings are **not channel-utilization
percentages**, and a single sample does not prove interference. At that stage,
the failed queries and empty neighbor results showed that radio reachability
was still unresolved; they did not establish distance, antenna damage, or
another specific cause.

## Final recovery validation after repositioning and reconnection

This was the final **radio-recovery** validation, before the later ESP32 core
migration below.

The coordinator was physically moved nearer the paired devices, with its
antenna attached and Ethernet/power restored. Once Ethernet returned, ZHA
loaded and reported **Z-Stack 20240710**, the same coordinator identity, and
the unchanged network channel **25**.

All **three previously failing uncached Basic manufacturer reads succeeded**:
two paired mains-powered outlets and one bulb responded. Fresh topology now
showed a router neighbor and active routes. This was live communication evidence,
not just cached availability or a successful integration startup. No channel
change or re-pairing was performed. Power had been restored to 8 dBm after the
earlier probe, and standard HA configuration retained no explicit transmit-power
override, with its default selection of 8 dBm. The ESP32 core remained `0.9.9`.
A fresh complete private backup captured after recovery again passed all twelve
identity, key, and counter comparisons against the pre-flash state.

Recovery was observed **after placement and reconnection**, but this was not
an isolated distance experiment. Power/reconnection and an external HA service
redeployment also occurred during the interval. The evidence therefore does
not prove that distance alone caused the problem, identify an antenna defect,
or establish firmware as the original cause. It confirms that the three tested
devices and routing checks recovered under the final conditions.

## USB core migration and current network status

The Synology host enumerated a CP2102N (`10c4:ea60`), passed temporarily to a
Linux guest with VMM's `--live` USB attachment. The guest required its matching
Ubuntu `linux-modules-extra` package and `cp210x`; no DSM host modules were
changed. See the [temporary passthrough guide](synology-usb-passthrough.md).

Initial transfers failed with both virtual UHCI and xHCI. Smaller 1 KiB packets
and a one-packet window alone did not cure the failures; the guest reported
USB `-71` errors and serial `EIO`. A dim yellow LED became bright after a power
cycle. With PoE plus USB connected, the complete backup and write subsequently
finished without USB errors. Power/cable/adapter causation was not isolated.

The full **16 MiB** backup comprises 13 read 256 KiB blocks and 51 all-`FF`
blocks verified against device MD5s. All block checks and the whole-device
MD5 matched; a second private copy passed SHA-256 verification. The actual
legacy partition table was read from this backup. No dump or private manifest
is published, and restoring the full dump was not tested.

The exact official **core `2.5.2` full image**, 2,004,768 bytes, was written at
`0x0` with esptool `5.4.0` at 115200 baud in **145.7 seconds**. The writer checked
the base MAC, chip/16 MiB flash identity, backup SHA-256, and current whole-device
MD5 before writing. It verified that secure boot and flash encryption were
already disabled; it did not change eFuses. No erase-all or
force option was used. Stock post-write verification and an explicit device
MD5 over the image both passed. The [USB guide](usb-core-upgrade.md) records the
exact public firmware checksum and guarded helper.

After reset, UART confirmed **firmware `v2.5.2`**, original SLZB-06, LAN mode,
a mounted 3456 KiB LittleFS, and `[ZBCHK] Connection OK`. The separate CC2652P
radio was not rewritten. These facts establish a successful core write and
boot, not post-migration communication with Zigbee end devices.

The temporary USB assignment was removed with `detach-device --live` and the
VM had no remaining USB hostdevs. Its matching module package was retained;
persistent VM settings and DSM host modules were unchanged. ZHA was re-enabled
without restarting HA, but entered `setup_retry` because the coordinator host
was unreachable. UART showed Ethernet link transitions without a DHCP address,
and a bounded host capture saw no coordinator Ethernet packets. The LAN path
is still under investigation; **post-core live Zigbee validation is pending**.

## Post-core switch and link checks

Read-only NSDP discovery from the Synology host identified the actual
**NETGEAR GS110TP**, distinct from a **GS308Ev4** discovered earlier. SNMP v2c
read queries to the GS110TP worked; no switch configuration writes were made.
The uplink reported **1 Gbps**. The coordinator's port was administratively
enabled but operationally down, while PoE reported `deliveringPower`.
Total reported power draw was approximately **1 W against a 46 W budget**.
Thus PoE supply and switch management access were present without a working
coordinator data link; these readings did not establish power quality at the
device or identify a failing component.

Existing PVIDs differed between switch ports. A random move to another PoE
port could therefore change LAN membership, so a cable/port comparison needs
to preserve the intended VLAN settings. The recorded VLAN differences do not
by themselves explain the physical operational-down state.

Core `2.5.2` UART continued alternating `ETH_CONNECTED` and `ETH_DISCONNECTED`
approximately every **12–14 seconds**, while switch observations showed the
port down and no device MAC/DHCP activity was seen. A completed **90-second**
UART capture contained one boot at serial-open start and no subsequent reboot
or panic. It recorded recurring Ethernet connect/disconnect pairs, the last at
80/82 seconds. At **61 seconds**, UART reported `EVENT_WIFI_AP_START`,
`Webserver started`, and `AP started`. These are firmware reports of fallback
AP/web startup; independent Wi-Fi association and web access were not tested.
No IP/DHCP was observed. After capture, the serial connection was closed and
the temporary VM USB assignment was removed and verified absent.

A controlled physical cable/port test was still pending. This is a bounded
observation, not proof that no reset could occur later or that firmware,
power, cabling, or the PHY has been isolated as the cause. **Post-core Ethernet
and Zigbee recovery remain unresolved.** Raw identities, credentials, and
network inventories are omitted.

## Limits and remaining options

- Radio firmware and ESP32 core have independent upgrade paths.
- A network firmware write is viable on this old core with a carefully adapted
  transport, but has erase/interruption risk and needs backups.
- The verified USB core migration required a working data/bootloader path;
  normal LAN access still needs separate post-boot validation.
- A fresh live response from real devices is the recovery criterion. Firmware
  version and integration status alone are insufficient. Three live reads
  and routing evidence validated the radio stage; those checks must be
  repeated after the subsequent core migration.
- Matter health is tracked independently; this radio write does not establish
  any change to Matter devices.
