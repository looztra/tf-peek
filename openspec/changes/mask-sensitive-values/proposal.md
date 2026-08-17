## Why

`tf-peek`'s primary surface is a GitHub PR comment, but `calculate_diff` ignores Terraform's
`before_sensitive` / `after_sensitive` markers entirely. Any attribute Terraform marks sensitive
(passwords, keys, connection strings) is rendered in plaintext into a durable, indexed,
notification-emailed artifact. This is documented as **D1** in
`docs/studies/2026-08-15-capability-and-market-analysis.md §4.1`, called out there as a release
blocker, and is already encoded as a `strict` `xfail` in `tests/integration/test_defects.py::test_sensitive_values_not_leaked` —
this change is what turns that test green.

## What Changes

- Parse `before_sensitive` / `after_sensitive` from the plan JSON (currently dropped by
  `models.Change`).
- `calculate_diff` masks any attribute Terraform marks sensitive as `(sensitive value)` instead of
  rendering its before/after values. **BREAKING**: this changes report output for any resource with
  sensitive attributes — previously-leaked plaintext values will no longer appear.
- Masking is conservative for nested attributes: Terraform's sensitivity marker for a nested
  block can itself be a nested `dict`/`list` rather than a flat `bool`. Since nested values are
  still rendered as a single blob (path-level diffing is out of scope here — see
  §5.3/1.5 of the study doc), if a sensitivity marker anywhere in a nested value's subtree is
  truthy, the **entire** value is masked rather than only the leaf. This is a scope boundary
  worth revisiting once path-level nested diffing lands.
- Add a `--show-sensitive` CLI flag to opt out of masking (off by default), matching the
  convention `tfplan2md` already established in this space.

## Capabilities

### New Capabilities
- `sensitive-value-masking`: attributes Terraform marks sensitive are masked in the rendered
  report by default, with an explicit opt-out flag.

### Modified Capabilities
(none — no existing spec currently makes a claim about sensitive-value handling)

## Impact

- `src/tf_peek/models.py`: `Change` gains `before_sensitive` / `after_sensitive` fields.
- `src/tf_peek/main.py`: `calculate_diff` gains a `sensitive` parameter; `generate` gains
  `--show-sensitive`.
- `tests/integration/test_defects.py`: removes the `strict` `xfail` marker from
  `test_sensitive_values_not_leaked` once it passes.
- No template changes — `report.md.j2` only ever consumes `res.diff`, so masking at the
  `calculate_diff` choke point is sufficient; no other code path renders raw before/after values.
