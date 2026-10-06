# Troubleshooting by layer

An outage can affect power, Ethernet, IP routing, the serial bridge, the radio,
and Home Assistant independently. Test each boundary before updating firmware.

## Power and Ethernet

- A PoE indicator proves supplied power; a link indicator proves an Ethernet
  link. Neither proves the switch uplink is connected to the household LAN.
- Confirm the PoE switch itself has an uplink, then check the DHCP lease and
  Ethernet MAC. An isolated powered switch can light both indicators without
  giving the coordinator a usable LAN path.
- Replace a suspect cable and test another known good port. In the case study,
  replacing the uplink cable restored switch/coordinator reachability.
- Test from the intended wired host. A different route, overlapping subnet,
  proxy, or VPN may reach an unrelated HTTP server. An nginx 404 is not proof
  that the coordinator's own web server is broken.
- Check uptime over several observations. A reboot immediately after an OTA
  attempt can be expected; recurrent spontaneous reboots require power/log
  investigation.

The legacy status command uses the `respValuesArr` HTTP header; the response
body is an HTML page, sometimes gzip-compressed. Parsing the body as JSON will
fail even on a working coordinator.

## Core mode, LEDs, and serial ownership

In core `0.9.9`, the blue LED indicates USB mode. A short button press toggles
USB/LAN mode and restarts the core. USB mode can leave Ethernet/web access off
unless the keep-web option is enabled. The old firmware's long press controls
LED behavior; do not substitute random long presses or a factory reset for
diagnosis. Later versions may use different controls, so consult their manual.

For network use, confirm `Zigbee-to-Ethernet`, the expected TCP port (typically
6638), and serial speed (115200 in the recorded setup). A serial connection
means a client is attached, not that the mesh is healthy. During radio flashing,
disable ZHA/Zigbee2MQTT and require no other serial client.

## USB does not enumerate on a Mac

Check the USB bus before troubleshooting serial drivers:

```sh
ioreg -p IOUSB -w0
system_profiler SPUSBHostDataType
ls /dev/cu.* /dev/tty.*
```

`SPUSBHostDataType` was the working USB data type on macOS 26; an older
`SPUSBDataType` command was not. A new USB device without a serial port points
toward driver/access/port-selection issues. **No USB device at all** points
earlier: cable data wiring, adapter, port, device hardware, or attachment.
Installing a serial driver cannot repair absent physical enumeration.

The manufacturer specifies a data-capable **USB-A to USB-C** cable for this
hardware generation, and documents USB-C-to-C limitations. A passive
USB-C-male-to-USB-A-female adapter is not a hub and need not appear as its own
USB device. Check cable data capability with another peripheral instead of
assuming every charging cable carries data.

PoE and USB can be connected together as documented by SMLIGHT. External PoE
power does not prove a C-to-C data connection will enumerate. In the case study,
multiple cable/adapter combinations, including C-to-C with PoE, produced no USB
device. The available evidence did not identify one definitive failed component.

Avoid cutting cables or improvising an injector. A verified data cable, a
known-good adapter, or the supported PoE/network radio path is easier to test.
An advertised USB-C power splitter is not automatically compatible with the
SLZB-06's data/attachment behavior.

## HA loaded, but Zigbee devices still unavailable

Distinguish these observations:

1. ESP32 HTTP responds.
2. TCP serial client is connected.
3. ZHA initialization completes and the live radio version is correct.
4. The intended network identity and keys are present.
5. An actual Zigbee device responds to an uncached request now.

Cached `available`, old LQI/RSSI, and a successful config-entry reload do not
establish item 5. Use `ha_zha.py live-read` against known mains-powered routers
and inspect recent HA logs privately. `NWK_NO_ROUTE` indicates failure to route
the Zigbee request; it is different from inability to open the TCP socket.

Check antenna attachment, original coordinator placement, interference, powered
mesh routers, and time since the outage. A coordinator temporarily moved beside
a Mac may be far from its former mesh neighbors. Battery devices may sleep;
do not use them as the sole immediate test.

Historical devices that were disconnected months earlier should not be counted
as newly broken. Compare last-seen timestamps and known intentionally unplugged
devices before judging recovery.

### Interpret radio probes without overdiagnosing

The [follow-up case-study checks](case-study.md#controlled-follow-up-radio-checks)
used a standalone client with ZHA disabled and the existing network retained.
The radio accepted 8 dBm and 20 dBm power requests, but paired-device address
queries timed out and `MgmtLqi` returned zero neighbors at both settings.
The original 8 dBm setting was restored. This does not isolate an antenna or
distance fault, and an accepted power command does not verify actual RF output.
Any separate diagnostic client needs exclusive ownership; it must not compete
with ZHA or Zigbee2MQTT or form a replacement network.

Energy-detection readings also need careful interpretation. A value expressed
as a fraction of the raw 0–255 scale is not the percentage of time a channel is
busy. The case study's single channel-25 sample at about 68% of that scale did
not establish interference. Do not change the network channel solely on that
sample or treat higher transmit power as a demonstrated fix.

### Confirm recovery with fresh device responses

In the [final case-study validation](case-study.md#final-recovery-validation-after-repositioning-and-reconnection),
the coordinator was repositioned nearer the paired devices and reconnected.
All three previously failing uncached reads then succeeded, and refreshed
topology showed a router neighbor and active routes. The radio stayed on
`20240710`, the channel and coordinator identity were unchanged, and no
re-pairing or persistent transmit-power increase was needed.

This supports checking placement and connectivity and then repeating the same
live tests. It does not prove distance as the unique cause: power/reconnection
and an HA service redeployment also occurred in that interval. Record those
confounding changes when describing recovery, and distinguish successful
responses from the tested devices from untested devices' cached status.

## Matter is a separate investigation

This original SLZB-06 is used here as a **Zigbee** coordinator. The documented
procedure does not repair Matter Server, IPv6/mDNS routing, Thread border
routers, or Matter credentials. A whole-house outage can affect both stacks at
once without giving them the same root cause. Verify HA's Matter integration
and server independently; distinguish intentionally powered-off nodes from
new failures. Do not factory-reset Matter devices to troubleshoot a Zigbee
coordinator.
