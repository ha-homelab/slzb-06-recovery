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
