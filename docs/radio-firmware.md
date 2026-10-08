# Updating the CC2652P coordinator over Ethernet

For where this fits relative to backups and the later USB core migration,
start with the [complete upgrade runbook](upgrade-runbook.md).

This procedure targets **original SLZB-06 / CC2652P / core 0.9.9**. It programs
the Zigbee chip through the ESP32 serial bridge. It does not update the core,
install a new ESP32 partition table, or convert the device into a Thread router.

For supported modern core firmware, prefer SMLIGHT's built-in radio updater.
The [manufacturer's radio guide](https://github.com/smlight-dev/slzb-06-manual/blob/main/docs/guide/flashing-and-updating/updating-cc2652p.md)
also describes manual Ethernet flashing, but warns that it depends on a stable
wired connection. A core that downloads the image locally before flashing has
different failure characteristics from streaming through an old TCP bridge.

## Firmware selection

The case study used `CC1352P2_CC2652P_other_coordinator_20240710.hex` from the
[official Koenkk release](https://github.com/Koenkk/Z-Stack-firmware/releases/tag/Z-Stack_3.x.0_coordinator_20240710).
For this original board the variant is **`other_coordinator`**, not LaunchPad,
P7, P10, router firmware, or an EFR32 image. Check the board label and the
[upstream adapter mapping](https://github.com/Koenkk/Z-Stack-firmware/blob/master/coordinator/Z-Stack_3.x.0/README.md).

`20240710` was selected because the upstream maintainer documented fixes for
crashes associated with `20230507` in
[discussion #505](https://github.com/Koenkk/Z-Stack-firmware/discussions/505).
It is the tested version here, **not a claim that it is the latest release**.

```sh
python3 scripts/fetch_firmware.py --out artifacts
```

The script downloads from upstream and checks both ZIP and extracted HEX hashes.
The ZIP SHA-256 is
`9622142c2e4d0d367148e6d54d4efa19be2877658328fdaa240a4df4655adbc0`;
the HEX SHA-256 is
`1e81ad785ecb733e83ab556446d6ece6de0d4346216c7c9621cf2dc8fa26bea7`.
No firmware binaries are stored in this repository.

## Why a legacy wrapper is needed

The current SMLIGHT flasher's automatic network bootloader command uses the
modern API numbering. In core `0.9.9`, action `4` means file listing; the
correct legacy bootloader command is **`/api?action=8&cmd=2`**. Calling it changes
the radio into bootloader mode and interrupts Zigbee operation. The wrapper
checks model, core version, and an operator-supplied Ethernet MAC first.

The old bridge's source uses a 256-byte buffer and a transmitted-length limit
of 255. The flasher's normal 252-byte blocks plus framing and a coalesced
acknowledgement can exceed that boundary. During the case study:

- The default block size failed at the first `SEND_DATA` after erase.
- 128-byte blocks progressed to roughly 24%, then a one-second `GET_STATUS` deadline
  expired even though the bridge log showed a response.
- **128-byte blocks, a minimum ten-second acknowledgement timeout, and ten
  milliseconds of pacing after each write** completed with matching CRCs.

This is a narrow compatibility workaround, not a general tuning recommendation.
The wrapper patches the pinned flasher in process; it does not modify installed
source files or send arbitrary bootloader flags. It does not offer `--force`,
bootloader disabling, or automatic repeated erase/retry.

## Prepare a wired Linux host

The successful run used an isolated Python 3.12 environment on a wired Linux VM.
A Synology-attached VM or another wired Linux machine can be suitable; there is
no requirement for a USB cable for this radio operation. Install the OS's
`libmagic` runtime if the Python dependency reports it missing.

```sh
python3.12 -m venv .venv-radio
.venv-radio/bin/python -m pip install --require-hashes -r requirements-radio.txt
.venv-radio/bin/python -m pip check
```

The upstream flasher depends on Linux GPIO packages even when this path uses
network serial. This environment was not validated on macOS. Use the Mac to
control the wired host over SSH if convenient; do the actual TCP flashing from
the wired host. Avoid VPN routes, HTTP proxies, and Wi-Fi in the flashing path.

## Back up and release the serial connection

Follow [Backups](backups.md), including a **fresh complete** ZHA network backup
and retained HA application data. Check the backup date and copy it privately
to the host running the flasher. A raw firmware file is not a network backup.

Find the ZHA entry ID, then disable that entry deliberately:

```sh
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test status
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  disable --entry-id REPLACE_WITH_ZHA_ENTRY_ID --execute
python3 scripts/slzb.py --url http://192.0.2.10 status
```

Require `Zigbee-to-Ethernet` mode and `connectedSocketStatus: No` before flashing.
If using Zigbee2MQTT, stop its actual service/container instead. Do not run both
stacks against the same serial radio. Check the external antenna and stable PoE
power, and keep the coordinator in a known good radio location.

## Dry run, then explicit programming

Substitute the actual host and Ethernet MAC. The first command is offline; it
checks the exact firmware hash and the presence of structured backup data.
It cannot verify that a backup belongs to the physical device or is recoverable.

```sh
.venv-radio/bin/python scripts/radio_legacy.py \
  --host 192.0.2.10 --expect-mac 02:00:00:00:00:10 \
  --firmware artifacts/CC1352P2_CC2652P_other_coordinator_20240710.hex \
  --network-backup backups/zha-before.json
```

To execute, append **both** `--coordinator-stopped --execute`. This performs
erase, write, CRC verification, and a radio reset. The erase can remove active
network state. Leave the integration disabled until the command completes.
Keep complete output privately and record the exit status. A progress bar
reaching 100% is not a substitute for successful CRC verification.

For the recorded image the segments were `0x00000..0x2bf38` and
`0x57fa8..0x58000` (exclusive ends). The successful run reported CRCs
`0x5884637b` and `0xed398d6d`, respectively. A mismatch or exception is failure.

## Reconnect and verify

```sh
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  enable --entry-id REPLACE_WITH_ZHA_ENTRY_ID --execute
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test status
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  backup --out backups/zha-after.json
python3 scripts/compare_network.py backups/zha-before.json backups/zha-after.json
```

Verify the running radio firmware from fresh ZHA startup diagnostics, not an old
device registry string or a web page cached before the reboot. Confirm the same
network identity and preserved keys, then test several mains-powered routers
using the uncached Basic-cluster read:

Initialization or restore can take several minutes. The lifecycle helper waits
up to five minutes for an enable/disable response. A request timeout does not
prove HA stopped processing it: query integration status and inspect logs before
retrying. `setup_in_progress` is neither successful recovery nor a final failure.

```sh
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  live-read --ieee 00:00:00:00:00:00:00:01
```

Use an actual paired router IEEE address. A sleeping battery device may need
waking and is a poor first health test. The helper sends a read, not an on/off
command, and does not test every cluster or appliance function.

If ZHA is loaded but `NWK_NO_ROUTE` persists, investigate antenna, coordinator
location, powered routers, mesh recovery, and recent response timestamps. Do
not immediately change the channel, form another network, or re-pair everything.

## If flashing fails after erase

Keep the host, PoE supply, and Ethernet path stable. Preserve the error output
privately. Determine whether the core HTTP interface still works and whether
the radio can still enter its bootloader. A radio in bootloader mode can make
ZHA fail to initialize even while the ESP32 remains healthy.

Recheck the exact image and hardware, the single-client requirement, and the
transport parameters before a deliberate retry. The case study recovered from
interrupted writes using the same validated image and bootloader; that is not
a guarantee for arbitrary failures. If the bootloader is inaccessible, stop
and follow SMLIGHT/TI recovery instructions. Disabling or overwriting bootloader
access may require an external hardware programmer.
