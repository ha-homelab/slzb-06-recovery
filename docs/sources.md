# Sources and evidence

Reviewed for the October 2026 recovery session. Web documentation and upstream
branches can change; consult the source matching your installed version.

## Manufacturer and upstream sources

- [Original SLZB-06 product page](https://smlight.tech/product/slzb-06/),
  [Thread guide](https://smlight.tech/manual/slzb-06/guide/thread-matter/), and
  [Bluetooth proxy guide](https://smlight.tech/manual/slzb-06/guide/bluetooth-proxy/):
  advertised hardware and version-dependent alternative roles. See
  [capabilities](capabilities.md) for the original/U-series distinction.

- [Legacy SLZB-06 firmware source](https://github.com/smlight-dev/slzb-06-firmware):
  `web.cpp` API enums, `/update` implementation, configuration export, and
  bootloader commands; `main.cpp` serial buffer and USB/LAN mode behavior.
  The later core `2.5.2` mode form, `/api2` mode/reboot requests, and `/ha_info`
  fields were checked against the running device's served UI/JavaScript and
  actual responses, not inferred from this legacy source.
- [ESP32 update guide](https://github.com/smlight-dev/slzb-06-manual/blob/main/docs/guide/flashing-and-updating/updating-esp32.md):
  supported migration methods and USB web-flasher requirements.
- [CC2652P update guide](https://github.com/smlight-dev/slzb-06-manual/blob/main/docs/guide/flashing-and-updating/updating-cc2652p.md):
  exact image family, web/USB/Ethernet/programmer options, stable wired transport,
  disconnecting the Zigbee client, and preserving bootloader access.
- [Official core firmware catalog](https://updates.smlight.tech/firmware/slzb06x/core/)
  and [SMLIGHT web flasher](https://smlight.tech/flasher/): authoritative firmware
  downloads and model-specific full-image manifests.
- [SMLIGHT CC flasher](https://github.com/smlight-tech/smlight-cc-flasher):
  external tool pinned to version `0.1.7` by this project.
- [Koenkk coordinator mapping](https://github.com/Koenkk/Z-Stack-firmware/blob/master/coordinator/Z-Stack_3.x.0/README.md):
  hardware-to-image matching.
- [Koenkk 20240710 release](https://github.com/Koenkk/Z-Stack-firmware/releases/tag/Z-Stack_3.x.0_coordinator_20240710)
  and [maintainer discussion #505](https://github.com/Koenkk/Z-Stack-firmware/discussions/505):
  the tested radio version and context for `20230507` instability.
- [ESP32 boot-mode selection](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html):
  ROM serial downloader and reset/boot signals.
- [esptool basic commands](https://docs.espressif.com/projects/esptool/en/latest/esp32/esptool/basic-commands.html):
  flash identification, read, write, and verification; this project's USB helper
  pins esptool `5.4.0` and uses its stock stub protocol with bounded reads.
- [Synology VMM specifications](https://www.synology.com/en-global/dsm/7.3/software_spec/vmm)
  and [libvirt attach-device](https://www.libvirt.org/manpages/virsh.html#attach-device):
  USB passthrough availability and temporary live attachment scope.
- [Home Assistant ZHA documentation](https://www.home-assistant.io/integrations/zha/)
  and [ZHA WebSocket source](https://github.com/home-assistant/core/blob/dev/homeassistant/components/zha/websocket_api.py):
  integration behavior and admin backup/live-read interfaces. The helper's
  commands were checked against installed HA source; upstream `dev` may differ.
- [zigpy application implementation](https://github.com/zigpy/zigpy/blob/dev/zigpy/application.py):
  network initialization and backup restore behavior, subject to version/state.
- [Interface MIB, RFC 2863](https://www.rfc-editor.org/rfc/rfc2863.html),
  [Power Ethernet MIB, RFC 3621](https://www.rfc-editor.org/rfc/rfc3621.html), and
  [Q-BRIDGE-MIB, RFC 4363](https://www.rfc-editor.org/rfc/rfc4363.html): separate
  interface administrative/operational state, PoE delivery, and VLAN/PVID data.

## First-hand community reports, not compatibility guarantees

- [SLZB-06 and HA 2024.9.2](https://community.home-assistant.io/t/smlight-slzb-06-and-ha-2024-9-2/773037):
  reports of `0.9.9` to `2.5.2` HTTP OTA and limitations afterward.
- [SLZB-06 firmware](https://community.home-assistant.io/t/slzb-06-firmware/952206):
  a newer unit accidentally downgraded to old firmware was recovered by OTA.
  A unit retaining newer partitions is not evidence that an original legacy
  partition layout can fit the same image.

## How to interpret this repository

**Observed** means an operation or result actually occurred on the case-study
unit: HTTP responses, version after reboot, failed and later successful live
reads, refreshed topology, matching radio CRCs, device-verified full-flash
backup/partition data, and the core write and UART boot. **Source analysis**
describes code or downloaded image metadata.
**Inference** connects those facts, such as a suspected cause of USB instability;
the legacy OTA slot capacity itself was confirmed from the device backup.
**Untested possibility** is explicitly labeled, such as a custom partition
migrator. None of these categories should silently substitute for another.
