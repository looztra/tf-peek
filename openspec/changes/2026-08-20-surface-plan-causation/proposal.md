## Why

The 🚨 Critical Changes section is the report's whole reason to exist (§3.3 of
`docs/studies/2026-08-15-capability-and-market-analysis.md`: hoisting it above the fold is called the
key UX decision), yet it asserts danger and never explains it. §4.2 M1 names discarded
`replace_paths` as the highest-value gap: a reviewer facing a 🚨 replace most urgently needs to know
*why* Terraform decided to replace it.

[`json-format` § Change Representation](https://developer.hashicorp.com/terraform/internals/json-format#change-representation)
says `replace_paths` is omitted when no attribute path caused the replacement, for example when a
resource was tainted. `action_reason`, a sibling field on the resource change, supplies complementary
context for tainted, requested and trigger-driven replacements and for deletions. Shipping
`replace_paths` alone would therefore leave a material class of changes unexplained.

Terraform documents `action_reason` values as display hints. They state the mechanism that selected
an action, not whether the operator intended it: a missing resource configuration can result from an
intentional removal or an unhandled rename, while a missing `for_each` key or out-of-range `count`
index can result from either an accidental addressing change or a deliberate scale-down. The report
will phrase those stated mechanics neutrally and will not classify any reason as expected,
unexpected, intentional or accidental.

## What Changes

- **Parse both causation fields.** `Change.replace_paths` (array of arrays of string/number steps,
  defaulting to empty) and `ResourceChange.action_reason` (an **open** `str | None`, not a `Literal` —
  the spec states reason codes "are display hints only and the set of possible hints may change over
  time. Users of this must be prepared to encounter unrecognized reasons").
- **Render the "why" in resource detail blocks.** A short form on the always-visible `<summary>` line
  (so a skimmer who never expands the block still gets it) and the full form in the block body.
- **Format replace paths in HCL style.** `["settings", 0, "tier"]` renders as `settings[0].tier`:
  numeric step → `[0]`, identifier-safe string step → `.tier`, any other string step → a quoted
  subscript such as `["kubernetes.io/role"]`. Rendered paths are sorted and de-duplicated.
- **Suppress only a redundant reason.** Paths plus `replace_because_cannot_update` render the paths,
  because they already identify what the provider cannot update in place. Any other stated reason,
  recognized or not, remains visible alongside paths. Neither field present → render nothing rather
  than inventing an explanation.
- **Phrase known reasons, pass through unknown ones.** Known codes map to neutral prose that mirrors
  Terraform's vocabulary; an unrecognized code is echoed verbatim behind a "reason reported by
  Terraform" preamble, so a future Terraform release degrades the hint instead of failing the parse.
  The phrasing describes the stated mechanism and never infers operator intent or severity.
- **State the replacement mechanism.** `change.actions` order is the only signal distinguishing
  destroy-then-create (`["delete", "create"]`) from `create_before_destroy`
  (`["create", "delete"]`); `ResourceChange.is_replacement` tests membership and therefore discards
  it today. A named order-sensitive property drives a body-only callout stating the **mechanism**
  ("destroyed before its replacement is created"), not a severity claim — destroy-first means
  downtime for compute, data loss for a bucket or disk, and a new secret value for a
  `random_password`, so the report reports the ordering and lets the reviewer apply it.
- **Causation survives `detail = "summary"`.** A summarized resource currently short-circuits to
  "Details hidden by configuration". A replace path is metadata, not a value, so suppressing values
  while keeping the explanation is the coherent reading of `summary`.
- **Harden the new string surfaces.** Path steps can carry map keys containing `|`, backticks,
  newlines, `<` and `&`. The Markdown-table context is the discipline `safe-value-rendering` already
  establishes; the `<summary>` line is an **HTML** context under `autoescape=False`, and today it is
  safe only by accident because it is fed `f"{rc.type}.{rc.name}"`, both HCL identifiers.
- Documentation: `docs/explanation/resource-tiers.md` (causation under `detail = "summary"`) and the
  study's §7 P1 1.3 status row.

**Not** in scope: any reason-based marker or classification, or any effect on tiering, `critical_on`,
`--fail-on-critical`, or exit codes. This change reports the causation metadata Terraform provides;
repositories continue to define danger through the existing tier system.

No **BREAKING** changes: additive plan fields and additive report content.

## Capabilities

### New Capabilities

- `plan-causation-rendering`: how the report explains its own verdicts. Owns replace-path formatting
  and ordering, neutral `action_reason` phrasing and unknown-code passthrough, the narrow
  `replace_because_cannot_update` redundancy rule, the replacement-mechanism callout, causation
  surviving `detail = "summary"`, and the escaping obligations of both new string contexts.

### Modified Capabilities

None. The change adds report content without changing an existing capability's requirements.

Deliberately **not** modified:

- `resource-tier-config` — no report option or reason-based policy is added. Existing tiers remain the
  sole repository-defined risk axis.
- `critical-section-rendering` — its requirements govern placement and grouping (before the summary,
  action then type). Causation is additive content inside a block whose position is unchanged.
- `safe-value-rendering` — its requirements are scoped to attribute *values*. A path step is not a
  value, and the `<summary>` HTML context it never covers needs `<` and `&` handling that the
  table-cell rules do not. The new capability carries its own escaping requirement and cites this one
  as the established discipline.
- `deterministic-report-output` — "byte-identical output for identical input" already binds the new
  content; the sorting and de-duplication requirement lives with the paths it orders.
- `cli-invocation` — no new flags or configuration options.

## Impact

- **Code**: `src/tf_peek/models.py` (both new fields, the replacement-mechanism property); a causation
  formatter alongside `src/tf_peek/formatting.py` (path rendering, neutral reason phrasing);
  `src/tf_peek/report.py` (`resource_entry` gains causation; the `is_summarized` branch at
  `report.py:92` stops short-circuiting it); `src/tf_peek/templates/report.md.j2` (the `<summary>`
  short form and the body callout in both the 🚨 and 🔍 detail macros).
- **Goldens**: both existing goldens move regardless of scope, because
  `tests/integration/fixtures/kitchen-sink.json:49` and `examples/demo-plan.json:65` already carry
  `replace_paths: [["settings", 0, "tier"]]` — the harness from
  `archive/2026-08-16-integration-test-harness` was already aimed at this feature.
- **Fixtures**: current coverage of these fields is three destroy-first replaces, **zero**
  `action_reason` values and **zero** `["create", "delete"]` orders. New fixture cases cover tainted,
  requested and trigger-driven replacements; paths plus `replace_because_cannot_update`; paths plus
  an unrecognized non-redundant reason; replace with neither field; representative deletion reasons
  phrased without intent classification; an unrecognized reason; a `["create", "delete"]` replace;
  a path containing a hostile map key; a multi-path replace exceeding the `<summary>` cap;
  duplicate/overlapping paths; and a `detail = "summary"` resource being replaced.
- **Tests**: unit coverage for the path formatter, neutral reason phrasing and the narrow precedence
  rule; integration coverage for both rendering contexts and unknown-code passthrough.
- **Docs**: `docs/explanation/resource-tiers.md` and the study's §7 P1 1.3 status row.
- **No changes** to `src/tf_peek/config.py`, `config.toml`, `resolve_tier`, `ResourceRule`, the `Action`
  enum, exit codes, `docs/reference/configuration.md`, or `docs/reference/cli.md`.
