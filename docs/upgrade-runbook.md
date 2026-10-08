# Complete upgrade and recovery runbook

Use this page as the ordered route through the project. It covers the original
**SLZB-06: ESP32 core, 16 MiB flash, and CC2652P Zigbee radio**. It does
not apply unchanged to SLZB-06M, P7, P10, U-series, or another flash part.
The [case study](case-study.md) preserves the chronological evidence; the
linked specialist guides explain each operation in more depth.

The route recorded here was:

1. Restore basic LAN access and privately back up core settings, HA, and Zigbee.
2. Establish that modern core OTA images cannot fit the actual legacy layout.
3. Upgrade the radio from `20230507` to `20240710` through legacy Ethernet,
   restore the same network, and verify actual device responses.
4. Establish reliable USB through Synology VMM and an Ubuntu guest; capture and
   verify all 16 MiB of ESP32 flash.
5. Write the exact official core `2.5.2` full image at `0x0` and verify its boot.
6. Restore post-core Ethernet through a network-path bypass, correct USB mode
   to LAN, and repeat the network/live checks.

**Completed:** radio write/CRC, same-network restoration, three successful live
reads before the core migration, full ESP32 backup, core `2.5.2` write/UART boot,
and **three new successful live reads after post-core Ethernet/TCP recovery**.
The final fresh complete network backup also passed all 12 comparisons against
the pre-core recovered-network backup.
The exact cause of the failed GS110TP PoE path was not isolated. Earlier
pre-core reads were kept separate from the final post-core checkpoint.

## 1. Identify the target and prepare private working files

Confirm the physical model label, two separate firmware versions, Ethernet
endpoint, operating mode, antenna, and power source. A powered PoE device or
reachable switch does not prove the coordinator has a working LAN connection.
Follow [layer-by-layer troubleshooting](troubleshooting.md) if HTTP/TCP is down.
Do not start by deleting ZHA, resetting its network, or re-pairing devices.

Use a wired Linux host for legacy radio flashing. The USB core step must run
on the machine that actually owns the USB serial port; the recorded path used
an Ubuntu VM on Synology. The Mac can control that host and hold a second
private backup copy. No household IP, MAC, or credential belongs in Git.

Clone the public tools on each execution host, or reuse an existing checkout:

```sh
git clone https://github.com/ha-homelab/slzb-06-recovery.git
cd slzb-06-recovery
```

If the USB-owning guest differs from the radio-flashing host, prepare the
checkout there as well and transfer needed backups over your private trusted
path. Never add those backup files to the public repository.

Run examples from this repository's root. Replace each placeholder with a
separately verified value:

- `192.0.2.10`: coordinator address, not the switch or HA address.
- `https://ha.example.test`: Home Assistant base URL.
- `02:00:00:00:00:10`: example **Ethernet** MAC in HTTP/radio commands.
- `02:00:00:00:00:11`: example **ESP32 base** MAC in USB commands. These are
  different identity checks; do not copy one value blindly into both.
- `/dev/ttyUSB0`: the exact attached CP2102N serial device; a verified
  `/dev/serial/by-id/` path is preferable when available.
- ZHA entry ID and device IEEE placeholders: obtain from the intended HA
  instance's private records and status output.

```sh
umask 077
mkdir -p backups artifacts
python3.12 -m venv .venv-ha
.venv-ha/bin/python -m pip install --require-hashes -r requirements-ha.txt
python3 scripts/slzb.py --url http://192.0.2.10 status
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test status
```

The HTTP helper targets core `0.9.9`; do not assume its API works on `2.5.2`.
HA access prompts for a token or uses `HA_TOKEN` supplied privately. Keep
command output and diagnosis logs private too. The firmware helpers default
to dry runs; status/backup commands intentionally read the specified system.

## 2. Capture all three backup layers

Before either chip is erased or written, complete [the backup guide](backups.md):

```sh
python3 scripts/slzb.py --url http://192.0.2.10 backup-core \
  --expect-mac 02:00:00:00:00:10 --out backups/core-before
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  backup --out backups/zha-before-radio.json
```

The first command saves all six legacy core JSON files and checksums. The
second creates a **new complete** ZHA network backup, rather than exporting
an arbitrary older backup. Require `is_complete: true`. Preserve an HA-managed
application backup as well, including configuration, `.storage`, ZHA registries,
and a consistent `zigbee.db`. Copy the backups to another private location.

Inspect the private backup's date and target identity. Network keys, key
sequences, frame counters, channel, PAN, extended PAN, coordinator IEEE, and
device mappings matter. The recorded 13 device mappings were under
`network_info`, not a top-level `devices` array. A firmware binary or ESP32 dump
does **not** replace this Zigbee backup.

**Checkpoint:** complete readable backups for this target, with retained HA
data and a second private copy. If a complete Zigbee backup cannot be created,
stop before a radio erase and diagnose that failure.

## 3. Choose the core migration path without repeating rejected OTA

The actual legacy partition table was later confirmed from device-verified
flash data at `0x8000`. Its two application slots were each **`0x140000`
(1,310,720 bytes)**, at `0x10000` and `0x150000`. Physical 16 MiB capacity did
not enlarge those slots.

The `2.0.14` OTA image is 1,481,376 bytes and the `2.5.2` OTA image is 1,939,232
bytes. Both exceed the installed slots. Both attempted uploads returned
HTTP 200 with body `FAIL`, and core `0.9.9` remained installed. The internal
updater error was not captured, but the capacity mismatch is confirmed.

Do not reproduce these failed uploads as a required upgrade step. Legacy
`POST /update` writes an inactive application; it does not repartition flash.
Never send a `-full.bin` image to that endpoint. The supported major-layout
migration uses a USB full image; no LAN TFTP recovery server was found, and
the ESP32 ROM downloader is serial. A custom network partition migrator is
theoretical and unimplemented here. See [core firmware and partitions](core-firmware.md).

The recorded workflow upgraded the Zigbee radio while `0.9.9` still bridged
Ethernet successfully, then migrated the core. That is an observed sequence,
not a claim that every unit must upgrade its radio first. If your radio is
already verified on the intended firmware/network, do not erase it merely to
re-enact this sequence. For a modern core use its supported radio updater;
the following wrapper deliberately accepts only the legacy `0.9.9` API.

## 4. Upgrade the CC2652P radio and restore the same network

Read [the radio guide](radio-firmware.md) before executing. For this board use
the exact **OTHER coordinator** image listed below, not LaunchPad, router,
P7/P10, or another radio family. `20240710` is the tested release, not a
statement that it is the latest available release.

On the wired Linux host:

```sh
python3.12 -m venv .venv-radio
.venv-radio/bin/python -m pip install --require-hashes -r requirements-radio.txt
.venv-radio/bin/python -m pip check
python3 scripts/fetch_firmware.py --out artifacts
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  disable --entry-id REPLACE_WITH_ZHA_ENTRY_ID --execute
python3 scripts/slzb.py --url http://192.0.2.10 status
```

Require Ethernet mode and `connectedSocketStatus: No`. ZHA or Zigbee2MQTT must
release the radio; there must be only one serial owner. For Zigbee2MQTT use its
own version-appropriate backup and service-stop procedure; the HA helper does
not manage it. Preserve stable power, wired transport, and the antenna.

Dry-run the narrow legacy wrapper:

```sh
.venv-radio/bin/python scripts/radio_legacy.py \
  --host 192.0.2.10 --expect-mac 02:00:00:00:00:10 \
  --firmware artifacts/CC1352P2_CC2652P_other_coordinator_20240710.hex \
  --network-backup backups/zha-before-radio.json
```

After the backup and ownership checks, rerun that command with
**`--coordinator-stopped --execute` appended**. This erases/writes/verifies the
radio; it is not an ESP32 update. The helper uses `smlight-cc-flasher 0.1.7`,
legacy `/api?action=8&cmd=2`, 128-byte blocks, at least ten seconds for an ACK,
and 10 ms pacing. In the recorded recovery, 252-byte blocks failed immediately
after erase; 128-byte blocks with the original one-second timeout failed later.
The complete adapted run finished in about six minutes.

Require successful completion and both segment CRCs, not just 100% progress:

```text
0x00000..0x2bf38   CRC32 0x5884637b
0x57fa8..0x58000   CRC32 0xed398d6d
```

Then reconnect the existing HA installation:

```sh
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  enable --entry-id REPLACE_WITH_ZHA_ENTRY_ID --execute
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test status
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  backup --out backups/zha-after-radio.json
python3 scripts/compare_network.py \
  backups/zha-before-radio.json backups/zha-after-radio.json
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  live-read --ieee 00:00:00:00:00:00:00:01
```

The tested zigpy installation restored its retained complete network backup
when the erased radio was unformed. That behavior is version/state-dependent;
retain HA data and use its supported restore procedure. **Do not accept a new
network or re-pairing flow as equivalent recovery.** Initialization exceeded
90 seconds; the helper permits five minutes for lifecycle requests. If a
request times out, check actual integration state before repeating it.

**Checkpoint:** fresh running radio version `20240710`, complete new backup,
all 12 identity/key/counter comparisons passing, and uncached responses from
several previously paired mains-powered devices. In this case, 13 device
mappings and 14 ZHA records including the coordinator remained. Initially all
three live reads still failed with `NWK_NO_ROUTE`. Only after repositioning
the coordinator closer to its paired devices and reconnecting did two outlets
and a bulb respond and routes return. No channel change or re-pairing occurred.
Power/reconnection and an HA redeployment also occurred, so distance alone was
not isolated as the cause. These successful tests were **before** core migration.

## 5. Establish USB and stop the Zigbee host again

Create another fresh complete ZHA backup after radio recovery and before
changing the core; then release ZHA again:

```sh
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  backup --out backups/zha-before-core.json
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  disable --entry-id REPLACE_WITH_ZHA_ENTRY_ID --execute
```

Use the [USB guide](usb-core-upgrade.md) and, for the recorded hosting path,
the [Synology VMM guide](synology-usb-passthrough.md). The required order is:

1. Verify USB data enumeration. The manufacturer specifies USB-A-to-C for the
   original board; a charging cable or passive adapter does not prove a data
   path. Initial Mac attempts, even C-to-C plus PoE, failed to enumerate.
   Do not cut cables or assume a driver fixes an absent USB device.
2. Identify the exact CP2102N `10c4:ea60` on the Synology host. Temporarily
   attach only its current bus/device with VMM `attach-device ... --live`.
   Inspect the existing guest xHCI controller and choose a free port; do not
   copy another VM's controller index. No persistent assignment was needed.
3. In the Ubuntu guest, install the official `linux-modules-extra` package
   matching `uname -r` if `cp210x` is missing, then load `cp210x`. The recorded
   kernel was `6.8.0-142-generic`. No DSM host-module change or VM reboot was
   needed. Verify which serial port belongs to that USB device.
4. Supply stable power. Both UHCI and xHCI paths initially failed with USB
   `-71`/serial `EIO`; smaller packets alone did not fix them. After a dim LED
   observation, a power cycle and **PoE plus USB** yielded successful full
   backup/write. This does not prove which power, cable, or adapter component
   caused earlier failures. PoE-switch uplink and USB data are separate paths.

The unsuccessful Mac USB and higher-baud attempts did not write flash. The
verified backup and write path used 115200 baud. Failure to enumerate USB is
not evidence that a partial firmware image was installed.

Keep one USB owner. Entering the ESP32 downloader stops its network application
even when only reading flash. The CC2652P is a separate chip and is not rewritten
by the following operations.

## 6. Capture and verify all ESP32 flash before writing

Inside the USB-owning host/guest:

```sh
umask 077
mkdir -p backups artifacts
python3.12 -m venv .venv-core
.venv-core/bin/python -m pip install --require-hashes -r requirements-core.txt
.venv-core/bin/python -m pip check
.venv-core/bin/python scripts/esp32_core.py \
  --port /dev/ttyUSB0 --expect-base-mac 02:00:00:00:00:11 \
  --confirm-model SLZB-06 \
  snapshot --out backups/esp32-before-core.bin
```

That is an offline dry run. Once ownership and identity are established,
rerun it with **`--controller-stopped --execute` before `snapshot`**. Global
USB-helper flags go before the subcommand. It pins esptool `5.4.0`, 115200 baud,
the ESP32/16 MiB JEDEC identity `0x1840ef`, and the expected base MAC. It verifies
secure boot and flash encryption are already disabled; it never changes eFuses.

The helper checks each 256 KiB block against device MD5, reading nonblank
blocks with the stock `READ_FLASH` protocol at 1 KiB/window 1. It generates
`FF` blocks only when their device MD5 matches an all-`FF` block, then checks
the complete image against a fresh whole-device MD5. The actual snapshot had
13 read blocks and 51 verified blank blocks. The standard 4 KiB/window 64
attempt had lost a packet; it was not accepted as a backup.

**Checkpoint:** final file is exactly 16,777,216 bytes, with a verified private
`.manifest.json`, matching whole-device MD5 and SHA-256, plus a second private
copy whose SHA-256 matches. A `.partial` file is not a backup. The public helper
does not resume; use a new output for another attempt. The private session
predecessor resumed only after rechecking saved blocks against the device.

Leave the target in downloader mode between snapshot and write. If normal
firmware runs and changes flash, the writer's current-device comparison will
require a new complete snapshot. Do not alter the manifest to bypass a check.

## 7. Write the exact core 2.5.2 full image and verify boot

Download the full image, not its OTA sibling:

```sh
curl --fail --location --output artifacts/slzb-06-v2.5.2-full.bin \
  https://updates.smlight.tech/firmware/slzb06x/core/slzb-06-v2.5.2-full.bin
.venv-core/bin/python scripts/esp32_core.py \
  --port /dev/ttyUSB0 --expect-base-mac 02:00:00:00:00:11 \
  --confirm-model SLZB-06 \
  flash-2.5.2 --firmware artifacts/slzb-06-v2.5.2-full.bin \
  --snapshot backups/esp32-before-core.bin \
  --manifest backups/esp32-before-core.bin.manifest.json \
  --receipt backups/core-write-receipt.json
```

This is another dry run. The exact image length/hash and complete backup
manifest must pass. To perform the write, repeat with
**`--controller-stopped --execute` before `flash-2.5.2`**. The connected target
must still match the entire backup. The helper writes only the fixed full
image at `0x0` with stock esptool, without erase-all or force. Its occupied
sectors, including bootloader and partition table, are necessarily replaced.

The recorded operation took **145.7 seconds at 115200**. Stock post-write
verification and an explicit image-length device MD5 both passed. After reset,
UART reported `v2.5.2`, `SLZB-06`, LAN mode, mounted 3456 KiB LittleFS, and
`[ZBCHK] Connection OK`. **Checkpoint:** verified bytes and actual boot are
separate requirements. Neither establishes an operational Ethernet link or
a responding Zigbee end device.

The public `esp32_core.py` is a generalized version of the private hardware
scripts. It has offline safety/protocol tests; this exact published helper
has not itself completed an end-to-end hardware flash. The private predecessor
performed the recorded operations with the same protocol and pre-write guards.
Core `3.3.1` was downloaded/inspected but **not installed or runtime-validated**;
the verified core target remains `2.5.2`.

## 8. Restore runtime connectivity and repeat live validation

Inspect the new core's supported UI/UART for its actual mode, serial speed,
network configuration, and version. Reapply compatible settings deliberately;
do not inject legacy JSON into a changed schema. Close USB serial clients and
detach the temporary VMM device with `detach-device ... --live`, then verify
it is absent. Keep the private backups; guest driver packages may remain.

Test the network and bridge separately. The verified final path was Ethernet
directly to the home switch without the GS110TP PoE path, while USB remained
connected to Synology for power/data. DHCP and HTTP returned at 100 Mbps, but
TCP 6638 still refused connections because the core was in **USB mode with
keep-web enabled**. A responding website does not establish a working bridge.

For confirmed original SLZB-06 hardware running **core 2.5.2**, follow the
[version-specific mode correction](troubleshooting.md#core-252-http-works-but-the-radio-tcp-port-does-not):
check `coordMode` (`2` means USB), select LAN in the UI, retain keep-web, save,
and reboot. The observed form used multipart fields `coordMode=0`, `keepWeb=on`,
and `pageId=1` at `/saveParams`; the reboot used `/api2?action=4&cmd=3`.
Require `coordMode=0` after reboot, working DHCP/IP, and an open bridge port.
Use this version's UI/API, not the legacy `0.9.9` action numbers. This mode
change does not require rewriting the radio or creating a new Zigbee network.

Re-enable ZHA and query its real state. Once Ethernet/TCP access works, perform
the same complete backup/comparison and uncached reads again:

```sh
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  enable --entry-id REPLACE_WITH_ZHA_ENTRY_ID --execute
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test status
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  backup --out backups/zha-after-core.json
python3 scripts/compare_network.py \
  backups/zha-before-core.json backups/zha-after-core.json
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  live-read --ieee 00:00:00:00:00:00:00:01
```

If ZHA was already enabled and retrying an unreachable endpoint, the actual
recovery used one reload of the existing entry instead of another enable:

```sh
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  reload --entry-id REPLACE_WITH_ZHA_ENTRY_ID --execute
```

The recorded reload returned `require_restart=false`; HA did not need a full
restart. Check `status` again, then run the fresh backup and live-read commands.

Repeat the live read for several known paired mains devices. Require the
intended running radio version, preserved identity/keys, acceptable counters,
fresh routes/neighbors, and actual responses. A host-unreachable `setup_retry`
is an Ethernet/IP boundary failure; repeated network restores or radio erases
are not a remedy. A loaded entry alone is not the final recovery checkpoint.

In this session the post-core link was initially unresolved: the correct GS110TP
was reachable, its uplink was 1 Gbps, and the coordinator received PoE while
its port was operationally down. A 90-second UART capture showed recurring
Ethernet events with no repeat reboot/panic after the initial serial-open boot;
fallback AP/web startup appeared at 61 seconds but association/web access was
not tested. Later authorized switch changes and their verification are tracked
in the [current network record](case-study.md#authorized-switch-reconfiguration).
All physical/LAG ports were deliberately moved into one existing LAN VLAN;
the change was saved and survived a verified switch reboot. The uplink and
PoE returned, but the coordinator port remained down with no DHCP/address/HTTP.
The switch's built-in cable test had reported normal at about 2 m; that did not
prove the full Ethernet path good. **The reboot did not complete recovery.**
Do not treat those case-specific changes as required firmware-upgrade steps.

The later direct-Ethernet bypass and USB-to-LAN mode fix did complete live
recovery. LAN mode survived reboot; ZHA loaded and directly reported radio
`20240710`, the unchanged coordinator IEEE, and channel 25. **Three new uncached
manufacturer reads passed after the core migration**: two paired mains outlets
and one CREE bulb. No actuator command, re-pairing, or channel change occurred.
The web UI's radio version could remain `-1`/stale, so the direct ZHA query was
used. See the [final case-study checks](case-study.md#final-post-core-recovery).

A newly created complete post-core ZHA backup contained 13 known addresses
and 13 key-table entries. **All 12 comparisons** against the fresh pre-core
recovered-network backup passed, including preserved identity/keys/sequences
and nondecreasing counters. This confirms the checkpoint for the tested
devices; it does not assert that every historical device is online.

Do not attribute every earlier failure to the later USB mode: the earlier
UART capture explicitly showed LAN mode. The GS110TP path's cable, port, PHY,
power, and interoperability possibilities were not isolated from one another.

Use [switch identity, power, link, VLAN, then DHCP](troubleshooting.md#separate-switch-identity-power-link-vlan-and-dhcp)
to isolate this boundary. Preserve VLAN membership when comparing ports.
Switch diagnostics reporting a normal cable or a supplied power budget do
not prove the full data path works. Matter remains a separate investigation.

## Recovery and rollback boundaries

- **Radio interruption:** preserve power and logs, check that the legacy core
  and CC2652P bootloader are reachable, then use the exact validated radio image
  and one serial owner for a deliberate retry. Follow the [radio failure guide](radio-firmware.md#if-flashing-fails-after-erase).
  Retain HA's supported network restoration path and a suitable complete
  backup; never lower counters or manufacture a replacement network to make
  a comparison pass. An inaccessible bootloader may require vendor/TI hardware
  recovery, which was not tested here.
- **Core interruption:** establish stable USB/ROM access first. A matching
  verified 16 MiB dump, its identity/hash manifest, an independent copy, and
  known hardware/security state are rollback prerequisites. A full restore
  would restore the old ESP32 layout/settings, not the separate CC2652P network.
  **Restoring this dump was not tested.** The helper intentionally does not
  supply a generic dump-write/force operation; use a separately reviewed
  vendor-compatible recovery procedure. Do not write an old partition table
  alone over the new application.
- **Settings or LAN failure after a verified boot:** diagnose mode, physical
  link, VLAN, and IP before deciding to reflash. Preserve new and old backups.
  A verified core image is not proof of working Ethernet, and an Ethernet
  problem is not proof the Zigbee network needs resetting.
- **Switch changes:** firmware migration does not require flattening VLANs.
  Any network redesign needs its own authorization, private before/after
  configuration, recovery access, and saved/effective-state verification.
  This repository supplies no automatic switch-reconfiguration command.

The complete device snapshot, HA/network backups, configuration exports,
checksums, UART captures, and switch before/after records were retained in
private local storage and an integrity-checked recovery archive. The archive
and its device identities are not published. Public source code and firmware
download checksums help reproduce the procedure; they are not a substitute
for your own private device-specific backups.

## Exact upstream artifacts used

These are reproducibility references, not a latest-version recommendation.
Firmware remains upstream; do not commit it or private backups here.

- Radio archive: [CC1352P2_CC2652P_other_coordinator_20240710.zip](https://github.com/Koenkk/Z-Stack-firmware/releases/download/Z-Stack_3.x.0_coordinator_20240710/CC1352P2_CC2652P_other_coordinator_20240710.zip).
  ZIP SHA-256: `9622142c2e4d0d367148e6d54d4efa19be2877658328fdaa240a4df4655adbc0`.
  Extracted `CC1352P2_CC2652P_other_coordinator_20240710.hex` SHA-256:
  `1e81ad785ecb733e83ab556446d6ece6de0d4346216c7c9621cf2dc8fa26bea7`.
- Core full image: [slzb-06-v2.5.2-full.bin](https://updates.smlight.tech/firmware/slzb06x/core/slzb-06-v2.5.2-full.bin),
  **2,004,768 bytes**, offset **`0x0`**. SHA-256:
  `f3fd6a6a8c59c257a18fe398f4d0748729b5df3349db8d4557e50f47a1f903c9`.
- Rejected legacy OTA attempt: [slzb-06-v2.5.2-ota.bin](https://updates.smlight.tech/firmware/slzb06x/core/slzb-06-v2.5.2-ota.bin),
  **1,939,232 bytes**. SHA-256:
  `04ab52f8e49088b6fc0de13c0e595aa1ddcae25d79771ad8a00b1c235a5a1a9f`.
- Rejected legacy OTA attempt: [slzb-06-v2.0.14-ota.bin](https://updates.smlight.tech/firmware/slzb06x/core/slzb-06-v2.0.14-ota.bin),
  **1,481,376 bytes**. SHA-256:
  `45734e4b2a8fc8723fe4541afbcbc95f403c108eb73e770ce46b600389b7a15c`.

The original model's architecture and alternative roles are in
[capabilities](capabilities.md); manufacturer, esptool, Zigbee, and switch-MIB
references are collected in [sources and evidence](sources.md).
