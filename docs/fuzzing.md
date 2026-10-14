# Release-candidate fuzz testing

The fuzz targets exercise this repository's host-side recovery guards using
synthetic data. They do not open USB devices, contact coordinators, download
firmware, flash chips, connect to Home Assistant, or read private backups.

## Targets and input boundaries

- `backup` mutates JSON backup containers through the actual backup selector
  and the before/after comparison logic. It checks explicit selection, ambiguous
  containers, missing fields and self-comparison of complete backups. Traversal
  rejects nesting beyond 128 levels or more than 10,000 visited/pending values.
- `identity` mutates MAC addresses, local serial-port names, base URLs and legacy
  status JSON through the production validators. Accepted strings must validate
  consistently, and accepted hardware identities must retain the expected model
  and synthetic MAC. Invalid field types must produce a validation error.

The checked-in seeds are invented test data. Use documentation-only addresses
and fake keys when adding cases; never upload real backups, network keys, flash
snapshots, device identifiers or user configuration as a corpus or crash sample.

## Execution policy

`.github/fuzz.json` defines two Atheris 3.1.0 targets, 60 seconds each and a
4,096-byte input limit. The shared release workflow runs these only for an
explicit RC on the public repository's default branch. PRs, pushes, beta,
nightly and stable runs do not start fuzz campaigns. Ordinary unit tests retain
small deterministic regressions for failures found during development.

The shared runner pins the source revision and toolkit revision, limits each
input's runtime and process memory, and removes network access during the
campaign. A successful report records actual engine execution counts and binds
them to the source commit, workflow attempt and manifest. It is release evidence
for these host tools, not a certification of hardware or firmware safety and
not an OSS-Fuzz enrollment badge.

## Local reproduction

On supported Linux x86-64 with Python 3.12:

```sh
python3 -m venv .fuzz-venv
.fuzz-venv/bin/python -m pip install --require-hashes --only-binary=:all: -r .github/requirements-fuzz.txt
.fuzz-venv/bin/python fuzz/fuzz_backup.py fuzz/corpus/backup -max_len=4096 -max_total_time=60 -timeout=10 -rss_limit_mb=2048
.fuzz-venv/bin/python fuzz/fuzz_identity.py fuzz/corpus/identity -max_len=4096 -max_total_time=60 -timeout=10 -rss_limit_mb=2048
python3 -m unittest discover -s tests -v
```

To reproduce one failure, pass its saved input file instead of the corpus
directory. First verify that the input contains only synthetic data. Reduce a
confirmed failure, add a deterministic regression, fix the production behavior
and run a fresh RC. Do not suppress an unexpected exception in the harness to
make the release pass. Reports from a different commit or a zero-execution run
cannot qualify the candidate. Hardware acceptance remains a separate manual
process described in the recovery runbook.
