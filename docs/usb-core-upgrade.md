# USB core snapshot and guarded 2.5.2 migration

This detailed procedure follows the backup and radio checkpoints in the
[complete upgrade runbook](upgrade-runbook.md).

**Recorded outcome:** a complete 16 MiB snapshot passed block and whole-device
MD5 checks, and its second private copy passed SHA-256 verification. The exact
2.5.2 full image was written and verified; UART then confirmed firmware 2.5.2
booting in LAN mode and communicating with the Zigbee chip. Later, bypassing
the GS110TP PoE path and restoring LAN mode from a subsequently observed USB
mode recovered Ethernet, ZHA, and three fresh post-core live device reads.
The [case study](case-study.md#final-post-core-recovery) separates those final
checks from the earlier pre-core successes and the intermediate failures.

This path is for the **original SLZB-06**, with ESP32 and the recorded 16 MiB
flash part (JEDEC ID `0x1840ef`). It is deliberately narrower than esptool.
The target firmware is only the official `slzb-06-v2.5.2-full.bin`, written at
offset `0x0`. Other revisions, chips, images, offsets, and unknown flash parts
are rejected. Confirm the physical board label: the ESP32 ROM cannot by itself
identify an SMLIGHT board model.

The public `esp32_core.py` helper generalizes the private scripts used for the
recorded hardware operations. Its guards and transfer handling have offline
tests; this exact published helper has **not** itself completed an end-to-end
hardware flash. The private predecessor used the same bounded-read protocol
and pre-write checks, with additional resume/retry handling described below.

## Establish the USB path

The Mac's connection remained unreliable, while a Synology host consistently
enumerated a **CP2102N, USB ID `10c4:ea60`**. Passing that USB device to a Linux
guest provided a different transport path. See [Synology VMM passthrough](synology-usb-passthrough.md).
A working USB enumeration or serial port is only the first checkpoint; sustained
read integrity must also pass.

Both the initial virtual UHCI path and a later xHCI path suffered transfer
failures. The guest reported CP210x USB errors `-71` and an `EIO` opening the
serial port. The user observed a dim yellow LED that became bright after a
power cycle. With **PoE plus USB** connected, the subsequent full snapshot and
write completed without USB errors. This sequence supports checking power and
the entire USB path; it does not isolate power, cable, adapter, or controller
choice as the cause.

Stop ZHA/Zigbee2MQTT, retain the [private configuration and network backups](backups.md),
and identify the exact serial device. Entering the ESP32 downloader temporarily
stops its normal network application, even for a flash **read**. The radio chip
is a separate target: this procedure does not update or erase CC2652P firmware.

Install a separate environment inside the machine owning the USB port:

```sh
python3.12 -m venv .venv-core
.venv-core/bin/python -m pip install --require-hashes -r requirements-core.txt
.venv-core/bin/python -m pip check
umask 077
mkdir -p backups artifacts
```

The helper pins **esptool 5.4.0**, uses 115200 baud, and takes an explicit local
serial port. `--expect-base-mac` is the **ESP32 base MAC**, which can differ from
the Ethernet MAC used by the legacy HTTP helper. Obtain it from trusted device
records or an independently identified device; do not accept an unexpected MAC
merely to make the guard pass. Logs, dumps, manifests, and receipts remain private.

## Read and verify a complete snapshot

First run the offline input check:

```sh
.venv-core/bin/python scripts/esp32_core.py \
  --port /dev/ttyUSB0 --expect-base-mac 02:00:00:00:00:10 \
  --confirm-model SLZB-06 \
  snapshot --out backups/esp32-before.bin
```

To actually read, add `--controller-stopped --execute` **before `snapshot`**.
The helper validates chip, base MAC, security state, and flash ID before reading.
It refuses secure boot, flash encryption, or an unknown security state. It
verifies those features are already disabled; it never changes eFuses or
disables security features. It creates a
new `.partial` file, then processes all 16 MiB in 256 KiB blocks:

1. Obtain each block's MD5 from the connected device.
2. Reconstruct an all-`FF` block only when its device digest exactly matches the
   digest of a 256 KiB all-`FF` block. This is not an assumption about unused space.
3. Read every other block using the standard esptool stub `READ_FLASH` protocol,
   with 1 KiB packets and one packet in flight; check its protocol digest and
   block digest.
4. Compare the complete assembled image with a fresh whole-device MD5.
5. Only after success, publish the final local file and its private manifest,
   including SHA-256, device MD5, identity, capacity, and transfer parameters.

The standard read attempt used 4 KiB packets and a 64-packet window; a packet
was lost, so that attempt did not establish a valid backup. Smaller packets
also failed before the final power/transport arrangement. The bounded read
changes protocol parameters rather than inventing a new wire protocol; it is
not by itself a proven cure. The successful snapshot contained 13 read blocks
and 51 device-verified all-`FF` blocks. MD5 checks verify transfer consistency;
the local SHA-256 records the saved image.

The helper refuses existing output paths and does not resume an incomplete
snapshot automatically. A `.partial` file is not a verified backup. Keep the
complete file and `esp32-before.bin.manifest.json` together and copy them to a
second private location. No restore of this dump is implied to have been tested.
The private session tool resumed saved blocks only after rechecking every
block against the current device MD5; mismatches were reread. This public
helper deliberately requires a new output for a new attempt instead of
exposing that recovery/resume machinery.

After a snapshot, the target intentionally remains in download mode. This
avoids normal application writes between the snapshot and the guarded flash.
If normal firmware runs and changes flash in between, the flash helper will
require a fresh snapshot rather than bypassing its freshness check.

## Validate the exact full image and plan the write

Download the full image from the [official core catalog](https://updates.smlight.tech/firmware/slzb06x/core/):

```sh
curl --fail --location --output artifacts/slzb-06-v2.5.2-full.bin \
  https://updates.smlight.tech/firmware/slzb06x/core/slzb-06-v2.5.2-full.bin
```

Expected length: **2,004,768 bytes**. SHA-256:
`f3fd6a6a8c59c257a18fe398f4d0748729b5df3349db8d4557e50f47a1f903c9`.
The helper checks both, along with the exact filename; it accepts no substitute
or generic “force” option.

```sh
.venv-core/bin/python scripts/esp32_core.py \
  --port /dev/ttyUSB0 --expect-base-mac 02:00:00:00:00:10 \
  --confirm-model SLZB-06 \
  flash-2.5.2 --firmware artifacts/slzb-06-v2.5.2-full.bin \
  --snapshot backups/esp32-before.bin \
  --manifest backups/esp32-before.bin.manifest.json \
  --receipt backups/core-write-receipt.json
```

This remains a dry run. It verifies local snapshot length/digests and a matching
identity manifest. A legacy private manifest missing the required identity or
verification fields is rejected; do not fabricate fields to bypass the check.

To program, add `--controller-stopped --execute` **before `flash-2.5.2`**. The
helper rechecks the connected ESP32 identity/flash part, refuses secure boot or
flash encryption before loading the stub, and compares its current whole-flash
MD5 with the backup. Only then does it use esptool's normal
`write_flash` at `0x0`, keeping the image's flash parameters and leaving
`erase_all` and `force` disabled. It verifies written bytes with esptool and a
device MD5, saves a private receipt, and requests a reset.

The recorded write took **145.7 seconds** at 115200 baud. Stock esptool's
post-write hash check and a separate device-MD5 check over the 2,004,768-byte
image both passed. After reset, UART reported firmware `v2.5.2`, device type
`SLZB-06`, LAN coordinator mode, a mounted 3456 KiB LittleFS, and a successful
Zigbee-chip connection. CC2652P firmware was not rewritten during this operation.

The write necessarily erases/replaces the sectors occupied by the full image,
including the bootloader and partition table. It is not the HTTP OTA procedure.
It does not wipe all other flash sectors or prove that old credentials were
removed from unused areas. A failure stops the helper; it never automatically
tries another image or repeats an erase.

## Validate boot and release passthrough

Check the actual running core version, Ethernet, operating mode, settings, radio
version, preserved Zigbee network, and uncached responses from real devices.
A verified write receipt is not proof of a successful boot or end-device recovery.
Recover settings through the new supported UI, without blindly injecting old
configuration files into a different schema. Keep the original dump private.

After all USB operations and serial processes stop, detach only the temporary
USB assignment as described in the VMM guide. Re-enable the intended Zigbee
host and verify it reconnects. Do not leave a temporary troubleshooting USB
attachment as an undocumented permanent VM dependency.

Immediately after the write, the temporary attachment was successfully removed with
`detach-device --live`, and no USB hostdev remained on the VM. ZHA was re-enabled
without restarting Home Assistant, but remained in `setup_retry` because the
coordinator host was unreachable. UART showed Ethernet link transitions and no
DHCP address; no coordinator Ethernet traffic was observed in a bounded host
capture. Those observations did not isolate an uplink, cable, configuration,
or firmware cause and did not establish post-core Zigbee recovery at that stage.
Subsequent saved switch changes and a verified reboot also did not restore
the link. Finally, direct Ethernet to the home switch without the GS110TP PoE
path restored DHCP and HTTP at 100 Mbps while USB remained connected to
Synology. The core was then observed in USB mode with keep-web enabled;
switching to LAN mode and rebooting restored TCP 6638 and ZHA. Three fresh
uncached device reads passed after that correction. See the
[final network outcome](case-study.md#final-post-core-recovery) and
[version-specific mode checks](troubleshooting.md#core-252-http-works-but-the-radio-tcp-port-does-not).

References: [esptool basic commands](https://docs.espressif.com/projects/esptool/en/latest/esp32/esptool/basic-commands.html)
and [core migration context](core-firmware.md).
