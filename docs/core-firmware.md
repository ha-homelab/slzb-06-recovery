# ESP32 core firmware: OTA, USB, and partition limits

This is the partition/background reference for the
[complete upgrade runbook](upgrade-runbook.md).

The core controls networking and the web UI. Its version is separate from
Z-Stack on the Zigbee chip. Check the exact model before downloading anything
from the [official firmware catalog](https://updates.smlight.tech/firmware/slzb06x/core/).

## What legacy HTTP OTA actually does

In the [0.9.9 source](https://github.com/smlight-dev/slzb-06-firmware),
`POST /update` accepts multipart field `update`, calls Arduino
`Update.begin(UPDATE_SIZE_UNKNOWN)`, and writes the inactive application slot.
It does not replace the flash partition table. The endpoint can return
**HTTP 200 with body `FAIL`**, and can reboot after failure. Neither HTTP success
nor a reboot establishes that the upgrade succeeded.

Only an **app-only `-ota.bin`** belongs at this endpoint. A full image contains
bootloader/partition data and must not be uploaded as an OTA application.

The **actual installed** legacy partition table was later read at `0x8000`
from a device-MD5-verified USB snapshot, and matched the downloaded official
`0.9.9` full image:

```text
nvs       offset 0x009000   size 0x005000
otadata   offset 0x00e000   size 0x002000
app0      offset 0x010000   size 0x140000 (1,310,720 bytes)
app1      offset 0x150000   size 0x140000 (1,310,720 bytes)
filesystem offset 0x290000 size 0x160000
coredump  offset 0x3f0000   size 0x010000
```

The downloaded `2.5.2` and `3.3.1` full images use:

```text
app0      offset 0x010000   size 0x640000
app1      offset 0x650000   size 0x640000
filesystem offset 0xc90000 size 0x360000
```

The modern table above describes the downloaded full images; the legacy table
was confirmed on the device itself. Physical flash capacity was 16 MiB despite
its small legacy OTA slots. A newer factory layout running an old application
can therefore behave differently from an original old layout.
Core `3.3.1` was only downloaded/inspected; it was not installed or tested at
runtime. The successful write and boot recorded here used `2.5.2`.

## Observed attempts

- `slzb-06-v2.5.2-ota.bin`: 1,939,232 bytes;
  SHA-256 `04ab52f8e49088b6fc0de13c0e595aa1ddcae25d79771ad8a00b1c235a5a1a9f`.
- `slzb-06-v2.0.14-ota.bin`: 1,481,376 bytes;
  SHA-256 `45734e4b2a8fc8723fe4541afbcbc95f403c108eb73e770ce46b600389b7a15c`.

Both actual uploads returned `FAIL`; the device came back on core `0.9.9`.
Both images exceed the **actually installed** 1,310,720-byte application slots,
as the later verified readback confirmed. Neither can fit that layout. The
internal updater error code was not captured. Repeating the same oversized
upload is not a useful recovery strategy.

There are [first-hand reports of 0.9.9 to 2.5.2 over HTTP OTA](https://community.home-assistant.io/t/smlight-slzb-06-and-ha-2024-9-2/773037),
including reports of limitations afterward. They do not establish compatibility
for every partition layout. The [manufacturer's migration guide](https://github.com/smlight-dev/slzb-06-manual/blob/main/docs/guide/flashing-and-updating/updating-esp32.md)
calls for its USB web flasher when crossing the legacy major-layout transition.

## Guarded OTA helper

For a separately verified compatible OTA image and **known actual slot size**:

```sh
python3 scripts/slzb.py --url http://192.0.2.10 ota-core \
  --expect-mac 02:00:00:00:00:10 \
  --image artifacts/compatible-ota.bin \
  --sha256 REPLACE_WITH_VERIFIED_IMAGE_SHA256 --slot-size 0x140000
```

This checks the filename, image marker, checksum, and supplied size, then exits
without contacting the device. The size above illustrates the legacy layout,
not an assertion about your device. Add `--execute` only after backups and a
supported compatibility decision. There is no override for an oversized image.
The helper's size argument is an operator-supplied fact, not an automatic probe.

## Preferred full core migration

1. Save all backups and record operating mode, serial speed, DHCP/static settings,
   and the integration's endpoint.
2. Establish USB data enumeration and identify the actual serial port.
3. Use the [official SMLIGHT web flasher](https://smlight.tech/flasher/) for the
   exact model and stable release. Its full image/offset metadata is authoritative.
4. Reapply appropriate settings through the new supported UI. Verify identity,
   Ethernet connectivity, core version, radio version, and the existing network.

Do not perform an indiscriminate erase as a troubleshooting step. When using
esptool manually, inspect the vendor manifest and image first; this project
deliberately supplies no universal full-image write command.

For the specific original board and image used here, the
[guarded USB helper](usb-core-upgrade.md) provides a complete snapshot and an
explicit 2.5.2 write path. That write and UART boot were verified; later,
Ethernet and three post-core live reads recovered after a network-path change
and a USB-to-LAN mode correction. See the [final validation](case-study.md#final-post-core-recovery)
and [2.5.2 mode/API checks](troubleshooting.md#core-252-http-works-but-the-radio-tcp-port-does-not).
The helper rejects different images,
unexpected identities, unverified backups, secure boot, and flash encryption.

## Can TFTP or the bootloader bypass this?

The ESP32 ROM download mode documented by
[Espressif](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html)
is a serial flashing path. It does not supply a LAN TFTP recovery server.
Ethernet and the old HTTP updater run in application firmware. No TFTP updater
was found in the legacy SLZB-06 source.

A custom application could theoretically migrate partitions or implement a
network recovery protocol, but it would need a careful relocation strategy,
validation, and recovery testing on this exact hardware. This project has not
implemented or validated one. Uploading a full image to `/update` does not
achieve that migration.
