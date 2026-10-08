# Security policy

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/ha-homelab/slzb-06-recovery/security/advisories/new).
If the form is unavailable, contact a maintainer through the repository's GitHub
profile to arrange a private channel before sharing sensitive details. Public
issues are for non-sensitive defects and feature requests.

Include the affected commit/release, prerequisites, a minimal synthetic
reproduction, expected and actual results, and impact. Do not include live
credentials, personal data or access to devices you do not own.

## Response and supported versions

Maintainers aim to acknowledge a private report within 14 days, investigate its
scope, and agree on remediation and disclosure with the reporter. If no reply
arrives within 14 days, follow up privately. Confirmed security defects are
prioritized by impact; critical defects take precedence over feature work.

Security fixes target the current default branch and latest published release,
where one exists. Older snapshots are not maintained security branches. Release
notes must identify security fixes, affected versions and upgrade actions without
disclosing credentials. This policy is a commitment for handling reports, not
a claim that no vulnerabilities exist or that past reports met a response SLA.

## Project boundary

This project provides attended backup, recovery and firmware helpers for the original SMLIGHT SLZB-06.

Coordinator backups contain Zigbee network secrets. Keep them outside Git and protect local copies. The legacy Ethernet path may use plaintext HTTP and serial-over-TCP; use a trusted isolated network. Verify the exact hardware, backup completeness, firmware digest and target before any write. Unit tests and command help never establish that a live device is safe to flash.

See [security design and validation boundaries](docs/security-design.md).
