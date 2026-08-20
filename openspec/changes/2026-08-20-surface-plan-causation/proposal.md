## Why

The 🚨 Critical Changes section is the report's whole reason to exist (§3.3 of
`docs/studies/2026-08-15-capability-and-market-analysis.md`: hoisting it above the fold is called the
key UX decision), yet it asserts danger and never explains it. §4.2 M1 names this the "highest-value
gap in the list": a reviewer facing a 🚨 replace most urgently needs to know *why* Terraform decided
to replace it, and tf-peek discards the field that answers that.

Reading the actual format spec while scoping this change turned a one-field feature into a two-field
one. [`json-format` § Change Representation](https://developer.hashicorp.com/terraform/internals/json-format#change-representation)
says `replace_paths` "will be omitted if the action is not replace, **or if no paths caused the
replacement (for example, if the resource was tainted)**." So `replace_paths` alone answers only the
provider-forced case; tainted resources, `-replace=ADDR` requests and dependency-driven replacements
carry their explanation in `action_reason`, a sibling field on the `resource_changes` element.
Shipping `replace_paths` without `action_reason` would leave the 🚨 section still silently
unexplained for a whole class of replaces — coverage, not polish.

`action_reason` also extends the same answer to **deletes**, which is the larger prize. Its enum
splits cleanly into one intentional cause and four accidental ones:

| `action_reason` | Cause | Reviewer reaction |
| :--- | :--- | :--- |
| `delete_because_no_resource_config` | removed from the configuration | expected |
| `delete_because_each_key` | `for_each` key no longer matches | usually an accident |
| `delete_because_count_index` | index outside the current `count` | usually an accident |
| `delete_because_no_module` | containing module no longer declared | usually an accident |
| `delete_because_wrong_repetition` | repetition mode changed (`count` ↔ `for_each`) | usually an accident |

"This production database is being deleted because a `for_each` key changed" is the canonical
Terraform footgun, and no tool in the study's §5.2 competitor table surfaces it. That distinction is
a fact about the plan, not a policy preference, which is why it can be rendered without touching the
tier system or growing a policy DSL.

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
- **Establish a precedence rule.** Paths present → render the paths (`replace_because_cannot_update`
  is implied by them and is suppressed as noise). Paths absent → render the phrased reason. Neither →
  render nothing rather than inventing an explanation.
- **Phrase known reasons, pass through unknown ones.** The nine documented codes map to prose that
  mirrors Terraform's own vocabulary; an unrecognized code is echoed verbatim behind a "reason
  reported by Terraform" preamble, so a future Terraform release degrades the hint instead of failing
  the parse.
- **Mark unexpected deletions.** The four addressing-slip reasons get a distinct 💥 badge;
  `delete_because_no_resource_config` deliberately does not, because the contrast is what makes the
  badge mean something.
- **Add a `[report]` config table with `highlight_unexpected_deletes` (default `true`)** as the
  opt-out for that badge. This is the first non-`[[resources]]` key in `peek_config.toml`.
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
- Documentation: `docs/reference/configuration.md` (the new table), `docs/explanation/resource-tiers.md`
  (causation under `detail = "summary"`), and the study's §7 P1 1.3 status row.

**Not** in scope: any effect on tiering, `critical_on`, `--fail-on-critical`, or exit codes. This
change is rendering-only. Reason-based escalation
(`always_critical_when_reason = ["delete_because_each_key"]`) is an attractive follow-up and is
explicitly deferred — `2026-08-18-fail-on-critical-gate/design.md` rules out a second policy
language, and the gate shipped two days ago.

No **BREAKING** changes: additive plan fields, additive config key, additive report content.

## Capabilities

### New Capabilities

- `plan-causation-rendering`: how the report explains its own verdicts. Owns replace-path formatting
  and ordering, `action_reason` phrasing and unknown-code passthrough, the paths-over-reason
  precedence rule, the unexpected-deletion badge, the replacement-mechanism callout, causation
  surviving `detail = "summary"`, and the escaping obligations of both new string contexts.

### Modified Capabilities

- `resource-tier-config`: gains the top-level `[report]` table and its
  `highlight_unexpected_deletes` key, so every `peek_config.toml` key stays specified in one place
  rather than splitting the config schema across two capabilities. The delta is purely
  `## ADDED Requirements`; no existing `[[resources]]` requirement changes.

Deliberately **not** modified:

- `critical-section-rendering` — its requirements govern placement and grouping (before the summary,
  action then type). Causation is additive content inside a block whose position is unchanged.
- `safe-value-rendering` — its requirements are scoped to attribute *values*. A path step is not a
  value, and the `<summary>` HTML context it never covers needs `<` and `&` handling that the
  table-cell rules do not. The new capability carries its own escaping requirement and cites this one
  as the established discipline.
- `deterministic-report-output` — "byte-identical output for identical input" already binds the new
  content; the sorting and de-duplication requirement lives with the paths it orders.
- `cli-invocation` — no new flags. The badge opt-out is a repo-level report-shape preference, the
  same family as tiers, not a per-invocation override like `--show-sensitive`.

## Impact

- **Code**: `src/tf_peek/models.py` (both new fields, the replacement-mechanism property);
  a causation formatter alongside `src/tf_peek/formatting.py` (path rendering, reason phrasing);
  `src/tf_peek/report.py` (`resource_entry` gains causation; the `is_summarized` branch at
  `report.py:92` stops short-circuiting it); `src/tf_peek/config.py` (a `ReportOptions` model and the
  `[report]` read in `load_config`, which today reads only `resources` and discards every other key);
  `src/tf_peek/templates/report.md.j2` (the `<summary>` short form and the body callout in both the
  🚨 and 🔍 detail macros).
- **Goldens**: both existing goldens move regardless of scope, because
  `tests/integration/fixtures/kitchen-sink.json:49` and `examples/demo-plan.json:65` already carry
  `replace_paths: [["settings", 0, "tier"]]` — the harness from
  `archive/2026-08-16-integration-test-harness` was already aimed at this feature.
- **Fixtures**: current coverage of these fields is three destroy-first replaces, **zero**
  `action_reason` values and **zero** `["create", "delete"]` orders. New fixture cases needed:
  tainted replace with no paths; `replace_by_request` with no paths; paths *plus*
  `replace_because_cannot_update` (redundancy suppression); replace with neither paths nor reason;
  `delete_because_each_key`; `delete_because_no_resource_config` as the no-badge contrast; an
  unrecognized `delete_because_*` code; a `["create", "delete"]` replace; a path containing a hostile
  map key; a multi-path replace exceeding the `<summary>` cap; duplicate/overlapping paths from one
  provider; and a `detail = "summary"` resource being replaced.
- **Tests**: unit coverage for the path formatter, the reason phrasing table and the precedence rule;
  config coverage for the `[report]` table, its default and a rejected unknown key inside it.
- **Docs**: `docs/reference/configuration.md`, `docs/explanation/resource-tiers.md`, and the §7 P1
  1.3 status row in the study.
- **No changes** to `config.py`'s `resolve_tier`, `ResourceRule`, the `Action` enum, exit codes, or
  `docs/reference/cli.md`.
