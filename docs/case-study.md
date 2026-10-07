# Recovery case study — 2026-10-06

This record removes household addresses, device identities, secrets, raw logs,
and private deployment details. It distinguishes observations from inference.
For the ordered procedure and runnable commands, use the
[complete upgrade and recovery runbook](upgrade-runbook.md).

**Final outcome:** radio `20240710` and core `2.5.2` were written and verified,
and **three fresh live Zigbee reads passed after the core migration**. Recovery
required bypassing the GS110TP PoE path and correcting a subsequently observed
USB coordinator mode to LAN mode. No channel change or re-pairing occurred.
The sequence below preserves earlier successes and intermediate failures;
the exact cause of the GS110TP path failure was not isolated.

## Starting point

After a household power outage, Home Assistant's Zigbee and some Matter devices
were reported unavailable. The Zigbee adapter was an original SMLIGHT SLZB-06,
with its legacy UI reporting ESP32-D0WDQ5 and 16 MiB physical flash,
core `0.9.9` (March 3, 2023),
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
The later USB ROM/esptool identification was **ESP32-D0WD-V3 revision 3.1**,
with a 40 MHz crystal. This differs from the legacy UI's chip-name string;
the UI string is not an independently confirmed packaging requirement.

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
was still under investigation at this stage; post-core live validation had
not yet succeeded. The later recovery is recorded below.

## Post-core switch and link checks

Read-only NSDP discovery from the Synology host identified the actual
**NETGEAR GS110TP**, distinct from a **GS308Ev4** discovered earlier. SNMP v2c
read queries to the GS110TP worked; no switch configuration writes were made.
This describes the discovery stage; a later separately authorized change is
recorded below.
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
power, cabling, or the PHY has been isolated as the cause. Post-core Ethernet
and Zigbee recovery were still unresolved at this stage. Raw identities, credentials, and
network inventories are omitted.

## Authorized switch reconfiguration

The operator later explicitly requested a flat switch configuration. This was
a separate network change, not a required part of flashing the SLZB-06. Private
before/after records were saved before changing it. All ten physical ports
and four logical LAG interfaces were assigned the same PVID and untagged
membership in one existing LAN VLAN. The old WAN VLAN was removed; the built-in
reserved VLANs had no member ports. The management address and management VLAN
were not changed. Actual VLAN numbers, port assignments, and inventories are
not reproduced here.

The old switch firmware did not accept identically interpreted egress and
untagged masks for every operation; some changes required separate SETs.
Completion was established by reading the **effective current VLAN table** and
all fourteen PVIDs, not by assuming a submitted mask meant what was intended.
The configuration save reported `savingComplete (3)`. These quirks are why this
project does not provide generic bulk SNMP mutation commands.

The built-in cable test on the coordinator port reported **normal**, with an
estimated length of **2 m**. The port nevertheless remained operationally down,
while the uplink was up at 1 Gbps. This diagnostic result did not prove the
cable, connectors, or either Ethernet PHY fully functional.

After confirming the configuration was saved, the operator authorized a
switch reboot. The reset request timed out as the switch went offline. The
first SNMP response, 36 seconds after polling began, showed a fresh 24-second
uptime. Comparison of **55 relevant values** before and after boot confirmed
that the effective VLAN memberships, static configuration, and all fourteen
PVIDs persisted. The uplink returned and the coordinator port again reported
PoE delivery, but its Ethernet link remained down, with no coordinator
DHCP/address/HTTP access. **The successful switch reboot did not restore the
coordinator Ethernet path or complete post-core Zigbee validation.**

The recovery archive remains private. It includes device/HA backups and
configuration records as well as the UART and switch observations; the original
16 MiB backup SHA-256 and archive integrity were rechecked. No private dump,
credential, device identity, or household topology is included in this repository.

## Final post-core recovery

The operator removed the GS110TP PoE path and connected Ethernet directly to
the home switch without PoE, while USB power/data remained connected to
Synology. The coordinator obtained DHCP at its original reserved address;
its Ethernet identity was checked privately. HTTP now worked at **100 Mbps**
and showed **core `2.5.2`**. This bypass recovered the LAN path, but did not
isolate a cable, port, PHY, power, or interoperability fault in the GS110TP path.

HTTP availability was not sufficient: the device was now in **USB mode**,
with `keepWeb=true`, and TCP **6638 refused connections**. The actual `2.5.2`
API returned `coordMode=2`, `/ha_info` reported `Info.coord_mode=2`, and UART
said `Coordinator mode: USB`; the blue mode LED matched that state. An earlier
UART boot had explicitly reported LAN mode, so this later USB mode does not
explain all preceding Ethernet failures. The operator also observed the blue
LED go off and return after about five seconds when using the button; the
reason for that behavior was not established.

After checking the actual `2.5.2` web form/API, coordinator mode was saved as
LAN (`coordMode=0`) with keep-web enabled and the core rebooted. The response
was `200 ok`, the mode query returned `0`, and LAN mode survived reboot. UART
confirmed LAN mode, DHCP/100 Mbps, and `[ZBCHK] Connection OK`; TCP 6638 opened.
The [version-specific mode guide](troubleshooting.md#core-252-http-works-but-the-radio-tcp-port-does-not)
records the exact form fields and endpoint distinction from `0.9.9`.

Reloading the **existing** ZHA entry once returned `require_restart=false`.
ZHA reached `loaded` and directly identified **Z-Stack `20240710`**, the same
coordinator IEEE, and unchanged channel **25**. Three fresh **uncached Basic
manufacturer reads all succeeded after the core migration**: two previously
paired mains outlets and one CREE bulb. No actuator command, re-pairing, or
channel change was performed. The core web UI's radio-version field could
remain `-1`/stale; the direct ZHA radio query was the version evidence.

A **new complete ZHA backup** was then created through
`zha/network/backups/create` with `is_complete=true`, 13 known network addresses,
and 13 key-table entries. Compared with the fresh recovered-network backup
from before the core migration, **all 12 checks passed**: coordinator IEEE,
channel/PAN/extended PAN, network and trust-center keys/sequences, and counters
that had not decreased. No private values are published.

This passes the post-core recovery checkpoint for the three tested devices;
it does not establish the state of every historical paired device. The GS110TP
path's exact failure cause remains unproven; the observed bypass and mode
correction established recovery under the final conditions, not a universal
GS110TP repair.

## Limits and remaining options

- Radio firmware and ESP32 core have independent upgrade paths.
- A network firmware write is viable on this old core with a carefully adapted
  transport, but has erase/interruption risk and needs backups.
- The verified USB core migration required a working data/bootloader path;
  normal LAN access required separate post-boot validation and correction.
- A fresh live response from real devices is the recovery criterion. Firmware
  version and integration status alone are insufficient. Three live reads
  and routing evidence validated the radio stage. A second set of three
  uncached reads after the core migration established final live recovery.
- Matter health is tracked independently; this radio write does not establish
  any change to Matter devices.
