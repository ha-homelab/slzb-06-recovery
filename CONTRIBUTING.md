# Contributing

Use [GitHub issues](https://github.com/ha-homelab/slzb-06-recovery/issues) for non-sensitive bug reports, questions and
feature proposals. Include the exact version/commit, environment, expected and
actual behavior, and a minimal sanitized reproduction. Check existing issues
first and keep follow-up evidence in the original thread. For vulnerabilities,
use the [private security process](SECURITY.md).

Submit a focused pull request against `main`. Describe the user-visible problem,
the resulting behavior, compatibility implications and checks performed. Preserve
existing authorship and third-party license/provenance records. Discuss changes
to protocols, storage, device safety or dependency/runtime requirements before
making an incompatible change. English is the common language for code review
and project documentation.

## Development and validation

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-ha.txt
python -m unittest discover -s tests -v
python -m compileall -q scripts
```

Python scripts run directly. Separate requirement files select Home Assistant, core-flash and radio dependencies; install only those needed for the documented operation. CI uses synthetic fixtures and never flashes a device.

The [CI workflow](.github/workflows/ci.yml) is the authoritative list of required jobs.
Use isolated test data and temporary outputs. Never run a device write, unlock,
deployment or publication command merely to validate a documentation change.

## Test and review policy

Changes to behavior must add or update automated tests that fail for the old
defect and cover the new boundary; regression fixes should include the relevant
failure case. If automation is infeasible, explain why in the PR and document
the reproducible manual procedure and limits. Update user/API documentation and
release notes for user-visible changes. Keep compiler, lint, static-analysis and
test assertions enabled, resolve new warnings, and document any remaining
warning with its reason and scope. Do not suppress a real security finding to
obtain a passing check. Wait for required checks and independent review before
merging; do not use an administrator bypass.

## Reproducible Python dependencies

The `.in` files declare direct dependencies. The corresponding `.txt` files pin
all resolved dependencies and approved archive SHA-256 hashes across supported
platforms. Install with `--require-hashes`; do not remove this check to work around
a missing archive. Review dependency updates and regenerate the locks with:

```sh
uv pip compile requirements-ha.in --generate-hashes --universal --python-version 3.12 --output-file requirements-ha.txt
uv pip compile requirements-core.in --generate-hashes --universal --python-version 3.12 --output-file requirements-core.txt
uv pip compile requirements-radio.in --generate-hashes --universal --python-version 3.12 --output-file requirements-radio.txt
```

Run the documented tests in a fresh virtual environment after updating a lock.

## Source releases

Use immutable Semantic Versioning tags (`vMAJOR.MINOR.PATCH`) for source snapshots.
The first source release is `v0.1.0`; do not move an existing release tag.
These versions identify the recovery helpers, tests and documentation. They are independent of ESP32 core and CC2652P radio firmware versions. Download firmware only through the documented upstream provenance checks; a source release does not flash a device or establish hardware acceptance.

Before tagging, identify the exact reviewed commit and verify its required CI
checks. Each release must link that commit and describe changes, upgrade
implications and security impact, including known limits. GitHub source archives
allow users to obtain the exact tagged tree; preserve all bundled licenses and
upstream notices. Report defects against the source tag or full commit ID.

## Review, rights and coding conventions

Follow [governance](GOVERNANCE.md) and the [code of conduct](CODE_OF_CONDUCT.md).
Submit only work you have the right to license under this repository's MIT
license; retain third-party notices and identify copied or generated material.
Python follows PEP 8 and the repository's configured lint rules. Shell scripts
must quote path and data arguments, check failures and keep execution explicit.
Update interface documentation and changelog entries when behavior changes.
Tests for new functionality and regression fixes are required unless the PR
explains why automation is infeasible and supplies a reproducible alternative.
Resolve new lint, compiler and analysis warnings before merging, or record a
specific reviewed false-positive explanation. Do not disable safety checks to
make CI pass. Keep test assertions enabled.

## Source-build dependency update boundary

The Renovate runner forbids package build-backend execution. The following inputs
and generated locks must therefore be reviewed and regenerated together in the
existing controlled build environment; this also applies to security updates.
GitHub vulnerability alerts remain enabled. Independent build, test and CI
dependencies retain their configured automatic update paths.

- `requirements-core.in` and `requirements-core.txt`: the USB core tooling requires esptool 5.4.0 without a usable wheel.

Use the existing regeneration command for each pair, then run its current CI
validation before accepting the source and lock together:

```sh
uv pip compile requirements-core.in --generate-hashes --universal --python-version=3.12 --output-file=requirements-core.txt
```

Do not make the shared update runner execute source builds to bypass this
boundary. Requalify native ownership only when the complete pinned dependency
closure can be resolved without build-backend execution.

## Security fixes for manually maintained locks

For a direct or transitive advisory in the manually maintained environment,
identify the affected package and the advisory's fixed version range. A plain
lock regeneration may retain the existing transitive pin. Replace
`AFFECTED_PACKAGE` below with the advisory's package name and request its update
explicitly in the existing reviewed build environment:

```sh
uv pip compile requirements-core.in --generate-hashes --universal --python-version=3.12 --output-file=requirements-core.txt --upgrade-package AFFECTED_PACKAGE
```

Review any direct or parent constraint that prevents selection of a fixed
release; qualify that constraint change together with the lock. Preserve the
documented interpreter, platform, hash and build-isolation requirements.
Check the resulting affected-package versions against the advisory's affected
and fixed ranges in every applicable Python/platform marker branch and every
coupled lock or export. A successful resolver exit alone is not proof of a fix.
If no compatible fixed resolution exists, keep the advisory open and document
the blocker instead of marking it remediated.

Preserve Python 3.12 and the separate core/radio/HA environments. Run the existing core dependency installation and synthetic checks; this qualification does not authorize flashing hardware.

Run the repository's complete existing dependency, runtime and CI qualification
before merging the source constraints and generated files together. GitHub
vulnerability alerts remain enabled for these manually maintained units.
