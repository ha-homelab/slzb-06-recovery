# Quality evidence and assessment limits

This project assesses its own application, host tooling and release sources.
Third-party platforms and physical-device acceptance remain explicitly separate.
The OpenSSF form is a project self-assessment, not an independent certification.

## Current verification — 2026-10-16

The checked local run used CPython 3.12.14 and the hash-locked HA dependencies:
`python -m unittest discover -s tests -v` passed 33 tests including real TLS 1.2/1.3
weak-chain rejection, firmware integrity, private output, identity, backup and
RPC guards. Fixtures never connect to or flash a real device. The strict TLS
profile is described in [security design](security-design.md).

The protected pull-request pipeline runs source/release contracts and security
analysis. Changes must pass required checks before merging; a skipped optional
job is not evidence that its analysis ran. Source and CI links in the public
assessment identify the reviewed revision. The complete first-party tree is
included in the security inventory, not just the tested runtime subset.

The GitHub issue inventory contains no non-pull-request bug or enhancement
reports. There are no published project security advisories or open Dependabot
alerts in the checked inventory. The maintainer confirmed knowledge of secure
design and common relevant implementation errors, and no reports outside GitHub
in the preceding 12 months. Human attestations are not inferred from test results.

Five open Scorecard findings describe badge adoption, code review, maintenance,
SAST and branch-protection posture. They are process observations, not confirmed
exploitable runtime vulnerabilities. CodeQL/security analysis and protected PR
checks must be inspected independently; a scanner failure is not zero findings.

## Remaining Silver work

There is no backup maintainer or tested one-week access recovery. Whole-project
statement coverage of at least 80%, a historical sample proving regression tests
for at least half of fixes, complete warning-as-error enforcement, reproducible
builds across independent environments and a complete assurance case have not
been established. These criteria remain unmet. Local test counts or scoped
coverage must not be substituted for those claims.

Keep historical fuzz and release-signature evidence tied to its actual release
and source revision. A later documentation or transport change does not rewrite
that history or automatically qualify a new stable release.
