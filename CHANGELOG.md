# Changelog

## [0.1.4] - 2026-10-18

### Changed

- Replace the obsolete Scorecard CI container with the reviewed, checksum-pinned scanner. Keep the upstream SARIF reporting policy, GitHub Security upload and retained report artifacts.
- Synchronize the source-suite version; packaged runtime behavior is unchanged.

### Upgrade

Unpack the verified host-tools archive into a new directory and preserve private backups, network keys, local configuration and the previous archive for rollback. Recovery operations remain explicit operator actions.

### Security

The replaced CI image contained 25 high-severity dependency findings in the recorded scan. The scanner replacement changes CI tooling, not the distributed application runtime. OpenSSF REST publication remains disabled as before. The archive contains host tools and synthetic tests, not firmware or private backups. No physical recovery or device compatibility is established by this CI change.

## [0.1.3] - 2026-10-17

### Changed

- Add an optional strong TLS host profile for firmware, coordinator and Home Assistant HTTPS/WSS clients, with real weak-chain rejection regressions.
- Refresh shared action revisions and correct security, recovery and release-fuzzing documentation.
- Document maintenance, private reporting and the limits of the OpenSSF evidence.

### Upgrade

Extract the host-tools archive into a new directory, preserve private backups and local configuration separately, and follow the existing explicit recovery procedure. Retain the previously accepted package for rollback. This release does not automatically modify devices.

### Security

The optional strong transport profile rejects weak certificate chains while retaining verified trust. Release validation uses synthetic inputs and does not establish physical-device recovery or include private backups, network keys or operator configuration.

## [0.1.2] - 2026-10-14

### Changed

- Validate each public release candidate with bounded, network-isolated fuzz campaigns against its exact source revision.
- Require positive engine execution counts, instrumented production code and validated seed corpora; retain source-bound reports and diagnostic evidence.
- Run deterministic seed and configuration checks in ordinary CI without starting mutation campaigns on betas.

### Upgrade

Use the existing installation procedure, preserve local configuration and keep the previous accepted package for rollback. This maintenance release updates release validation and does not change the application configuration format. Deployment and applicable device or integration acceptance remain separate from publication.

### Security

RC publication rejects absent or invalid source-bound fuzz reports. The fuzz runner bounds corpus paths, file types and size. No application vulnerability or new target-device acceptance is claimed by these tooling changes.

## [0.1.1]

### Added

- Versioned source distributions with explicit file inventory and isolated archive acceptance.
- RC-only fuzzing of synthetic backup selection/comparison and hardware identity validators.

### Fixed

- Malformed legacy status field types now return validation errors.
- Deep or excessive backup containers stop within a bounded traversal budget.

### Upgrade

Extract the host-tools source archive into a new directory and install only the
locked dependency set required by the selected tool. Preserve all private
backups separately. Existing device-specific recovery procedures and explicit
execution flags still apply; this release performs no automatic device changes.

### Security

Fuzzing and package acceptance use only synthetic data. No firmware, private
backups, network keys or operator configuration are distributed. The new input
guards fail before any device operation; hardware recovery remains manual.
