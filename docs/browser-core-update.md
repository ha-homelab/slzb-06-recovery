# Update the ESP32 core from the browser

For an ordinary update with working USB access, start with the official
**[SMLIGHT firmware updater](https://smlight.tech/flasher)**. It supports the
SLZB-06 family and uses ESP Web Tools: connect USB, select the **exact physical
model**, choose the firmware and follow the browser's install prompts. A local
Python environment is not needed for that write step.

The longer procedures in this repository document a difficult **legacy recovery**:
restricted OTA partitions, unreliable USB transfers, preserving a full flash
snapshot and verifying that the existing Zigbee network still worked afterward.
Those checks are useful when recovery is necessary; they are not prerequisites
for every routine installation. This repository does not republish SMLIGHT
firmware and its own release archive is not a device image.

## Before connecting

1. Confirm **original SLZB-06 / ESP32 + CC2652P**, not SLZB-06M, P7, P10 or MG24.
   This repository's recorded recovery applies to the original model; the vendor
   updater offers other products with different firmware.
2. Save your [configuration and Zigbee network backups](backups.md). Stop
   ZHA/Zigbee2MQTT while an updater owns the device. Keep the recovery copies
   private; they may contain network keys.
3. Decide which firmware target you intend to update. The **ESP32 core** provides
   Ethernet/web/serial transport. The **CC2652P radio** provides Zigbee and keeps
   network state. Updating one is not an update of the other.
4. Use stable power and a USB data cable on a desktop browser with Web Serial.
   Current Chrome or Edge is the straightforward supported route. Close other
   serial applications before connecting.

## Browser update and verification

Open the vendor updater, grant the serial port for the identified unit, select
its correct model and the intended **core** firmware, and review any erase or
reset warning before installing. Do not choose radio replacement firmware just
because it is also offered. Preserve the existing network; do not erase/re-pair
it as a routine response to a core update.

After restart, confirm the core version, Ethernet address, **LAN versus USB
operating mode**, serial bridge port, radio version and controller reconnection.
Then obtain fresh responses from existing Zigbee devices. These checks matter:
a completed progress bar does not prove that the network is working.

## When the guarded recovery path is still needed

Use [USB core recovery](usb-core-upgrade.md) if you need a complete verified flash
snapshot, exact pinned `2.5.2` image, identity/flash-size checks, or diagnosis of
unstable USB. The published helper and browser updater have different guarantees:
the browser flow does not replace this repository's full-flash freshness check
or independently establish a restorable backup.

Do not reproduce the old failed OTA sequence merely because it appears in the
case study. Start with [troubleshooting by layer](troubleshooting.md), identify
the actual failure, and choose the narrower relevant procedure.

## Troubleshooting

- **No serial port:** confirm a data cable, CP210x driver where required, OS
  permissions and correct USB connection. Close log viewers and other tabs.
- **No Web Serial:** open the vendor HTTPS site in a supported desktop browser,
  not an embedded preview or iPhone/iPad browser.
- **Disconnects or repeated write errors:** stop retries and diagnose power,
  cable and USB transport. Do not compensate with an unrelated image or erase-all.
- **Web UI works but Zigbee does not:** verify LAN/USB mode, TCP bridge settings
  and the single controller connection before changing radio firmware.
- **Wrong model shown:** disconnect and identify the physical device. ESP chip
  detection alone cannot establish the SMLIGHT product variant.

The browser route is documented from the vendor's supported interface; this
repository's recorded physical acceptance remains the separately described
[guarded recovery outcome](case-study.md#final-post-core-recovery).
