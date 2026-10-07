# Troubleshooting by layer

An outage can affect power, Ethernet, IP routing, the serial bridge, the radio,
and Home Assistant independently. Test each boundary before updating firmware.
For the complete ordered upgrade path, start with the
[upgrade and recovery runbook](upgrade-runbook.md).

## Power and Ethernet

- A PoE indicator proves supplied power; a link indicator proves an Ethernet
  link. Neither proves the switch uplink is connected to the household LAN.
- Confirm the PoE switch itself has an uplink, then check the DHCP lease and
  Ethernet MAC. An isolated powered switch can light both indicators without
  giving the coordinator a usable LAN path.
- Replace a suspect cable and test another known good port with the same
  intended VLAN membership and PVID. In the initial case-study stage,
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

### Separate switch identity, power, link, VLAN, and DHCP

Identify the actual switch before interpreting its management data. A familiar
brand name or a previously discovered address is insufficient when multiple
switches share a vendor. Match the reported model and the physical unit/port
using private records. In the case study, read-only NETGEAR Switch Discovery
Protocol (NSDP) queries from the intended LAN interface found a **GS110TP**;
an earlier same-brand discovery had identified a different **GS308Ev4**.
No discovery packets, addresses, or raw switch inventories are published here.

Using the switch UI or existing authorized read-only SNMP access, check each
layer independently:

1. **Power:** PoE detection/delivery state, current consumption, and available
   budget. `deliveringPower` confirms the switch is supplying power; it does
   not establish an Ethernet data link or prove power integrity at the device.
2. **Link:** uplink speed and the coordinator port's administrative and
   operational states. `admin-up` means enabled; `oper-down` means it is not
   operational. Compare these with the device's timestamped Ethernet events.
   A link-event loop is not by itself evidence that the ESP32 is rebooting.
3. **VLAN:** record the coordinator port's untagged/tagged membership and PVID,
   plus the uplink's path to the intended network. A random port swap can
   change LAN membership even if both ports deliver PoE. VLAN configuration
   is a separate forwarding check, not an explanation by itself for a physical
   link remaining down.
4. **Addressing:** once link and forwarding work, check learned device MAC,
   DHCP activity/lease, and the expected IP path. A reachable switch management
   interface does not establish reachability of a device on another port/VLAN.

The standard MIBs distinguish [interface state](https://www.rfc-editor.org/rfc/rfc2863.html),
[PoE delivery](https://www.rfc-editor.org/rfc/rfc3621.html), and
[VLAN/PVID configuration](https://www.rfc-editor.org/rfc/rfc4363.html).
Keep community strings, credentials, identities, and inventories private.
These observations require no SNMP SET or switch configuration change.
The later [authorized switch redesign](case-study.md#authorized-switch-reconfiguration)
was separate from those read-only checks and is not a general recovery step.

In the [post-core switch checks](case-study.md#post-core-switch-and-link-checks),
the uplink was 1 Gbps, while the SLZB port supplied PoE but stayed operationally
down. About 1 W total draw against a 46 W budget did not show budget exhaustion;
it did not rule out a device-side power, cable, port, or PHY problem. A controlled
physical cable/port comparison was still pending. Keep one variable at a time
and preserve VLAN membership when performing that comparison.

A built-in switch cable test later reported a normal cable of about 2 m while
the coordinator port remained down. Treat that as one test result, not proof
of a working Ethernet path. Saving the explicitly requested flat VLAN setup,
rebooting the switch, and verifying 55 persisted values also failed to restore
this port's link. A successful switch reboot or preserved VLAN configuration
does not substitute for checking the device port, DHCP, and actual HTTP/TCP.
On old firmware, inspect effective egress/untagged membership and PVIDs after
changes; a successful SET response alone is not evidence of the intended result.

Keep UART observation long enough to distinguish repeated link events from
an actual boot sequence and delayed fallback behavior. In this session, core
`2.5.2` logged fallback Wi-Fi AP and web-server startup at 61 seconds while
Ethernet transitions continued. A 90-second capture showed one initial boot
when the serial connection opened, with no subsequent reboot or panic.
Record serial-induced resets separately from spontaneous ones. An AP-start
log offers another diagnostic
avenue, but does not prove that a client can associate or open the web UI.
Check the device's actual AP configuration and verify those steps separately;
do not infer restored Ethernet or Zigbee communication from the log alone.

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
device on the Mac initially. A later [Synology-to-Linux USB path](synology-usb-passthrough.md)
enumerated CP2102N. Sustained reads still failed with USB `-71` and serial `EIO`
until a power cycle and PoE-plus-USB arrangement; the complete backup/write then
passed. Neither xHCI nor smaller packets alone had cured those failures. A dim
LED was an observed clue, not proof of a specific power/cable/adapter fault.

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

In the [radio-stage validation](case-study.md#final-recovery-validation-after-repositioning-and-reconnection),
the coordinator was repositioned nearer the paired devices and reconnected.
All three previously failing uncached reads then succeeded, and refreshed
topology showed a router neighbor and active routes. The radio stayed on
`20240710`, the channel and coordinator identity were unchanged, and no
re-pairing or persistent transmit-power increase was needed.

Those live successes preceded the subsequent ESP32 migration. After core
`2.5.2` was written and its boot verified, Ethernet had link transitions without
a DHCP address and ZHA retried an unreachable host. The [post-core checks](case-study.md#usb-core-migration-and-current-network-status)
are still pending. Diagnose this LAN boundary before attributing the retry to
the Zigbee mesh or reusing earlier successful device reads as current evidence.

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
