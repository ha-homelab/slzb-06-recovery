# Release-candidate fuzz testing

See the [illustrated RC fuzzing process and verified rollout results](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/rc-fuzzing-results.md)
for the shared release flow, evidence requirements and a dated cross-project
snapshot. The project-specific scope and reproduction guidance below still apply.

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
campaign. Diagnostic logs record actual engine execution counts. The report binds
the campaign outcome to the source commit, workflow attempt and manifest. It is release evidence
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


## Deterministic preflight in ordinary CI

For relevant changes in a public repository, the existing CI configuration
contract job installs the hash-locked Python 3.12 fuzz dependencies, runs
`pip check`, and replays the committed corpus with Atheris `-runs=0`.
This is deterministic seed replay: it does not start the timed mutation
campaign. Timed fuzzing remains exclusive to release candidates. The shared
preflight has a four-minute total budget, including dependency setup.

The `preflight-paths` entries in `.github/fuzz.json` select the relevant
production, dependency and harness changes. Shared contract, manifest and
workflow changes also trigger this check; missing comparison history runs
the check conservatively. Unrelated changes can skip this extra replay.

Before replay, the shared helper verifies that the following declarations
refer to project-local Python functions already instrumented by the
harness. Missing import instrumentation fails the check instead of
silently counting executions with incomplete feedback:

- `radio_legacy.find_network_backup`
- `compare_network.compare`
- `esp32_core.normalize_mac`
- `esp32_core.validate_port`
- `slzb.validate_base_url`
- `slzb.validate_identity`

Update these declarations when production functions move or are renamed.
They prove that the selected code is instrumented; they do not prove
exhaustive path coverage. Keep positive and rejected-input corpus cases
and independent semantic assertions alongside the existing unit tests.

## Artifact selection and retries

Release artifacts use `-run-<run_id>-attempt-<run_attempt>` names, and the collector selects only the current run and attempt.

Before publication starts, use **Re-run all jobs** only if the allocator and
release policy permit reuse of that run's reservation. Recreate every required
input in the same attempt; failed-only or individual retries can leave inputs
missing, and older artifacts must not fill those gaps.

For a fresh candidate or final build, once publication has started
(`begin_publication`), or its external publication result is partial or uncertain,
inspect the existing release, tags and assets before retrying. A consumed build
number requires a new workflow run and reservation authorized by the release
policy; an existing immutable tag may also require a new base version. Never
reset the release ledger, overwrite assets or retag to force a retry. Historical
byte promotion of an accepted RC keeps its reserved number and follows the
existing promotion policy.

Fuzzing still requires an explicit RC dispatch from the default branch of a public repository. Its report identifies one source revision and run; it does not prove complete platform coverage or device acceptance. Package receipts additionally bind fresh package publication to the current repository, source SHA, run ID and attempt. Historical promotion and retained-evidence validation keep their existing checks; complete package-set coverage remains a separate requirement. See [the shared evidence contract](rc-fuzzing.md).

### Package receipt identity

Fresh publication verifies each staged package receipt against the independently
supplied repository, source commit, workflow run and attempt. Receipts created
before this migration, or offline without an Actions identity, cannot qualify a
fresh publication. Run all required producers in one complete workflow attempt
after migration; an earlier attempt cannot fill missing inputs.

Historical promotion and retained-evidence validation keep their existing checks.
Receipt coverage validates the staged files; the expected packages and platforms
still require a separate completeness check. Existing release approval and device
acceptance policies continue to apply.

See the shared [receipt migration guide](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/release-workflow.md#migrate-package-receipt-identity-without-replacing-the-release-engine).

### Complete package producer inventory

`versioning.required_build_receipts` declares the exact package and signature
receipt filenames required by this project's final publisher. Each authenticated
receipt must match the repository, source commit, workflow run and attempt. A
missing producer or an unexpected receipt stops fresh publication, even when the
remaining packages are valid. RC fuzz evidence is checked separately; pre-signing
checks do not require a signature receipt that has not been created yet.

Before publication begins, rerun all required producers only when the allocator
and release policy permit reusing that reservation. After publication begins or
its outcome is uncertain, inspect existing tags, releases and assets before a
policy-authorized new run; never reset the ledger or mix earlier-attempt packages.
Historical RC promotion keeps its accepted source policy. Keep this explicit
inventory aligned with producer changes; it does not replace package-format,
signature or device acceptance checks.
