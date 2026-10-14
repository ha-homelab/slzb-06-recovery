# Changelog

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
