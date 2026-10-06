# Device capabilities and other options

This project concerns the **original SLZB-06**, not the newer SLZB-06U or other
radio variants. The [original product page](https://smlight.tech/product/slzb-06/)
lists a CC2652P radio, ESP32 core, LAN8720 Ethernet interface, and CP2102 USB/UART
bridge. Its advertised options include Zigbee-to-Ethernet, USB, and Wi-Fi modes,
with IEEE 802.3af PoE or USB power. SMLIGHT documents simultaneous PoE and USB
connection. Availability and controls depend on installed firmware.

The product page's “current page” link now leads to a newer U-series product
with different core/Ethernet hardware. Do not transfer its recovery promises or
firmware images to the original board.

## Zigbee roles and host software

Use coordinator firmware with **one** ZHA or Zigbee2MQTT owner. Moving between
USB and Ethernet changes the transport; it does not turn the coordinator into
another Zigbee network by itself. Wi-Fi mode is an advertised transport option,
but was not used or validated in this recovery.

SMLIGHT also offers Zigbee **router** firmware. That makes the device a member
of another coordinator's mesh; it no longer serves the existing network as
its coordinator. A role conversion needs its own migration plan and is not a
repair step for missing devices.

## Thread and Bluetooth: separate, untested projects

The [vendor's Thread guide](https://smlight.tech/manual/slzb-06/guide/thread-matter/)
describes replacing radio firmware with a Thread RCP and connecting an OpenThread
Border Router/HA stack. The guide lists core `2.1.0-dev` or later for its workflow.
This is not a feature established on the case-study core `0.9.9`, and does not
mean simultaneous Zigbee and Thread on its single CC2652P radio.

The [vendor's Bluetooth proxy guide](https://smlight.tech/manual/slzb-06/guide/bluetooth-proxy/)
describes ESPHome-based core firmware and compatible combinations. It warns
that the normal web UI is replaced and returning to factory firmware can need
USB. With unresolved USB enumeration, that is a significant recovery limitation.
No Thread, Bluetooth-proxy, or ESPHome conversion was tested here.

## What this session proved

It proved a guarded legacy Ethernet **radio** upgrade and restoration of the
same Zigbee network. Modern core OTA was rejected. After subsequent coordinator
repositioning/reconnection, the three previously failing live device checks
passed and routing returned; the exact cause was not isolated. Full USB core
migration and vendor-documented hardware-programmer recovery remain separate
options. See the [case study](case-study.md),
[core guide](core-firmware.md), and [radio guide](radio-firmware.md).
