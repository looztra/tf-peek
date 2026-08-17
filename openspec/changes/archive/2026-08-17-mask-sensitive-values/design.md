## Context

`calculate_diff` (`src/tf_peek/main.py:24`) is the single point where `before`/`after` values
become the `res.diff` dict that `report.md.j2` renders — confirmed by grep, every template path
that prints a value reads `res.diff.items()` and nothing else touches raw `before`/`after`. So
masking has exactly one place to happen; no template changes are needed.

`models.Change` (`src/tf_peek/models.py`) currently has no `before_sensitive`/`after_sensitive`
fields — Pydantic silently drops unknown keys from the plan JSON, so this data is available on
disk today and simply never reaches the model. See proposal.md for the motivating defect (D1).

Terraform's sensitivity marker shape: for a scalar attribute it's a `bool`. For an attribute whose
value is a nested object/array, Terraform *may* instead emit a nested `dict`/`list` mirroring the
value's shape, marking sensitivity per-leaf (confirmed by the fixture note carried over from the
`integration-test-harness` change's design.md — "`before_sensitive`/`after_sensitive` may be
`bool`/`dict`/`list`"). tf-peek does not yet do path-level nested diffing (that's a separate,
larger change — study doc P1 item 1.5 / D4b) — nested values are still rendered as one blob per
top-level attribute.

## Goals / Non-Goals

**Goals:**
- Close the plaintext-leak gap for both flat and nested sensitivity markers, without waiting on
  path-level nested diffing to exist.
- Single, obvious point of enforcement (`calculate_diff`) so there's no second code path to forget.

**Non-Goals:**
- Per-leaf masking inside a nested value (mask only `settings.password`, show `settings.tier`
  unmasked). Requires path-level diffing (D4b) to exist first — out of scope here. This change
  masks the whole attribute conservatively instead.
- Detecting sensitivity heuristically (e.g. by attribute name). Only Terraform's own
  `before_sensitive`/`after_sensitive` markers are consulted.

## Decisions

**D1. Mask at `calculate_diff`, not at the template.**
It's the only choke point (see Context), so it's also the only place a fix can regress from. A
template-level check would need to duplicate the same "is any of this subtree sensitive" logic
with no additional benefit.

**D2. Sensitivity check is "any truthy value in the subtree", applied per top-level key.**
For a given top-level attribute `k`, look at `before_sensitive.get(k)` and `after_sensitive.get(k)`.
If either is `True` (flat case), or is a `dict`/`list` containing any truthy leaf at any depth
(nested case), mask the whole attribute. This is a small recursive "any truthy" walk over a
`dict | list | bool`, not a merge or path-tracking structure — it only needs to answer
"sensitive anywhere?", not "sensitive where?", because the value itself isn't path-diffed yet.

*Alternative considered*: only handle the flat `bool` case now, and treat nested sensitivity as
"future work alongside D4b." Rejected — D1 is framed as a release blocker specifically because of
plaintext leakage; leaving a known nested-leak shape unmasked in the same change that claims to
close D1 would be an incomplete fix, not a staged one.

**D3. Masking checks both `before_sensitive` and `after_sensitive` independently, union of the two.**
Terraform can mark an attribute sensitive on only one side (e.g. a value that becomes sensitive, or
stops being sensitive, across the change). Masking if *either* side flags it is the conservative
choice and avoids a one-run window where a sensitive value briefly renders in plaintext depending
on which side of the diff Terraform happened to flag.

**D4. Placeholder text is the literal string `(sensitive value)`.**
Matches the exact wording the study doc's P0 recommendation used, and reads unambiguously as "a
value existed here and was withheld" rather than looking like a null/empty diff.

**D5. `--show-sensitive` is a plain boolean Typer option, default `False`.**
Mirrors the existing `--config`/`--output` option style in `generate()`. No config-file equivalent
(e.g. a TOML key) is introduced — this is a per-invocation display choice, not a classification
rule, so it doesn't belong in `PeekConfig`/`peek_config.toml` alongside the tier rules.

## Risks / Trade-offs

- **[Risk]** Conservative whole-value masking hides non-sensitive sibling data inside a nested
  block that has *any* sensitive leaf (e.g. `settings.tier` becomes invisible because
  `settings.credentials.password` is sensitive). → **Mitigation**: acceptable pending path-level
  diffing (D4b); documented as a Non-Goal above so it isn't mistaken for an oversight when that
  later change lands and narrows the mask.
- **[Risk]** `--show-sensitive` re-introduces the original leak if someone flips it on for a CI
  job whose output is public. → **Mitigation**: off by default; this is an explicit, named opt-out
  the operator has to type, not a default.
- **[Trade-off]** This is a **BREAKING** change to report output (previously-visible plaintext
  disappears). No deprecation window — the study doc frames the current behavior as a security
  defect, not a feature, so there's nothing to deprecate.

## Migration Plan

No data migration. Deploy as a normal release: land the fix, remove the `strict` `xfail` marker
from `tests/integration/test_defects.py::test_sensitive_values_not_leaked` in the same change
(leaving it would make CI fail per `strict=True`), update the CLI reference doc for the new flag.
No rollback concern beyond a normal revert — the change only affects rendered output, not stored
state.
