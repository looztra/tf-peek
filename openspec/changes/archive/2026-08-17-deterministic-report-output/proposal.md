## Why

`calculate_diff` derives attribute keys from a Python `set`, so the same Terraform plan can render in a different order under different `PYTHONHASHSEED` values. This churns sticky PR comments, prevents meaningful report diffs, and makes golden snapshots unreliable; the integration defect ledger already reproduces the failure across fresh interpreters.

## What Changes

- Render each resource attribute diff in deterministic lexical key order instead of hash-dependent set iteration.
- Audit report-producing collection traversals and order every output-observable unordered collection deterministically.
- Promote the existing D2 integration and unit assertions from strict expected failures to passing regression tests.
- Preserve report content and semantic grouping; only nondeterministic ordering may change.

## Capabilities

### New Capabilities
- `deterministic-report-output`: identical Terraform plan input produces byte-identical Markdown report output across Python hash seeds.

### Modified Capabilities
- None.

## Impact

- `src/tf_peek/main.py`: diff-key traversal and any identified output-observable unordered traversals.
- `tests/integration/test_defects.py`: D2 subprocess and unit regression tests.
- `tests/test_main.py`: unit coverage if the deterministic ordering contract is maintained there.
- `docs/studies/2026-08-15-capability-and-market-analysis.md`: mark P0 item 0.2 complete after the implementation is verified.
