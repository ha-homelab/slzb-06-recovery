# Backups and restoring the same Zigbee network

Back up **before** any erase/write operation. Use a private destination on the
machine doing the work, copy it to a second secure location, and check that it
can be read. A checksum detects changed bytes; it does not prove restore works.

## Three independent layers

1. **ESP32 configuration and optional full flash**: network settings, operating
   mode, serial parameters, authentication, and Wi-Fi settings. These are not
   a substitute for a Zigbee network backup.
2. **Zigbee network backup**: coordinator IEEE identity, channel, PAN ID,
   extended PAN ID, network/trust-center keys, key sequence, counters, and
   device-related information. These are secrets. A new network using the same
   channel is not the same Zigbee network.
3. **Home Assistant application backup**: ZHA configuration entry, `zigbee.db`,
   `.storage`, entity/device registries, and the surrounding HA configuration.
   Prefer an HA-managed full backup. Database copying needs consistency.

For Zigbee2MQTT, back up its complete data directory and coordinator backup
using the procedure for the installed Zigbee2MQTT version. The HA helper here
does not operate on Zigbee2MQTT.

## Export legacy ESP32 configuration

```sh
umask 077
mkdir -p backups
python3 scripts/slzb.py --url http://192.0.2.10 backup-core \
  --expect-mac 02:00:00:00:00:10 --out backups/core-before
```

Use the actual Ethernet MAC. The helper requires original `SLZB-06` and core
`0.9.9`, creates a new directory with mode `0700`, and writes mode `0600` files.
It refuses to overwrite existing files. Do not publish the resulting files.

The six `/config` files exported are `configEther.json`, `configGeneral.json`,
`configSecurity.json`, `configSerial.json`, `configWifi.json`, and `system.json`.
The helper also saves status and SHA-256 metadata. A failed export leaves a
partial directory that must not be treated as complete. Export currently
requires the unauthenticated legacy API; it does not disable device security.

To restore settings after a full core upgrade, use the new firmware's supported
interface and compare each relevant setting. Do not blindly inject legacy JSON
into a different configuration schema or restore the old partition table over
new firmware.

## Make a fresh ZHA network backup

Create a virtual environment and install the HA client dependency:

```sh
python3 -m venv .venv-ha
.venv-ha/bin/python -m pip install -r requirements-ha.txt
umask 077
mkdir -p backups
.venv-ha/bin/python scripts/ha_zha.py --url https://ha.example.test \
  backup --out backups/zha-before.json
```

The helper prompts privately for an HA long-lived access token, or reads
`HA_TOKEN` when your credential mechanism already supplies it. Do not put a
token directly on a command line or in a committed script.

It calls the admin WebSocket command `zha/network/backups/create`, allows up to
90 seconds, and requires `is_complete: true`. It then records current network
settings alongside the new backup. This differs from merely exporting an old
entry returned by `zha/network/backups/list`. The API was verified in the HA
version used for the case study; future versions can change it. If HA rejects
the command, use ZHA's supported backup UI and confirm completeness and date
before proceeding. Do not substitute an old backup without understanding the
network-key/counter consequences.

A zigpy backup can contain device mappings in `network_info.nwk_addresses` and
`network_info.key_table`, without a top-level `devices` list. Therefore
`len(backup.get("devices", [])) == 0` does **not** prove the backup is empty.

## Preserve Home Assistant state

Create and download an HA-managed backup. If an additional SQLite snapshot is
needed, use SQLite's backup API against `zigbee.db` (on a host where that file
is accessible), rather than copying only the main database while WAL writes
continue:

```sh
umask 077
sqlite3 /private/ha-config/zigbee.db \
  ".backup '/private/backup/zigbee.db'"
sqlite3 /private/backup/zigbee.db 'PRAGMA integrity_check;'
```

`ok` checks database integrity, not Zigbee radio restore compatibility.
Use a private HA backup for `.storage` and configuration. Never print complete
config entries, tokens, network settings, or backup contents into public logs.

## Optional full-flash backups

If USB enumerates and the ESP32 ROM loader is reachable, use official
`esptool` to identify physical flash capacity first, then read that exact range
to a private file. Example **only after confirming a 16 MiB part**:

```sh
python -m esptool --port /dev/ttyUSB0 flash-id
python -m esptool --port /dev/ttyUSB0 read-flash 0 0x1000000 backups/esp32-before.bin
```

This captures the ESP32, not the CC2652P. It may contain credentials. A CC2652P
raw flash read through an appropriate TI/SMLIGHT tool is a separate operation
and may not be available when debug/read protections apply. The case study
had no usable ESP32 USB connection, so no full ESP32 flash backup was obtained.
Do not claim a rollback path that was not actually captured and verified.

## After radio programming

Keep existing HA data and restore/reconnect through the installed integration's
supported procedure. In the tested zigpy setup, an unformed radio triggered
restore from its latest retained complete network backup. This behavior is
version- and state-dependent; it is not permission to discard backups or accept
forming a new network. Stop and investigate if HA offers a new-network flow.

Create `backups/zha-after.json` after recovery, then compare:

```sh
python3 scripts/compare_network.py backups/zha-before.json backups/zha-after.json
```

Require the same coordinator IEEE, channel, PAN, extended PAN, and key material.
Transmit counters must not move backward; a restore may intentionally advance
them. The helper requires both key records, sequence numbers, and transmit/receive
counters. Missing fields cause a failure rather than a misleading all-true
result. Containers with multiple unselected backups are rejected; export the
intended complete backup explicitly. The helper prints only equality/monotonicity
results. Also inspect the
reported **running** radio version and do live device reads. Matching network
identity is necessary, but not sufficient, for restored device communication.
