## Why

The capability & market analysis (`docs/studies/2026-08-15-capability-and-market-analysis.md`, item
1.1 in §7's P1 table) identifies a CI exit-code gate as the single highest-leverage change available:
the tiering engine already computes exactly the signal a gate needs (`rule.tier == "critical"` and
`action in rule.critical_on`), so turning that into a process exit code is a small change with an
outsized effect — it converts tf-peek from "nicer plan renderer" into "risk gate with an excellent
report attached" (§6), a category with no other occupant in the market map (§5.1).

Discussed live with the maintainer while scoping this change: an all-or-nothing gate is not enough.
The concrete example given was wanting to fail CI only when a resource is being **deleted**, even if
the same run's report also surfaces a critical **replace** elsewhere. Two real needs are distinct
here: (1) the common case — "fail on whatever the report already calls out as 🚨" — and (2) a
narrower, invocation-time override — "fail only on this specific action, regardless of what the
repo's `peek_config.toml` considers critical enough to render in the 🚨 section." Collapsing both into
one boolean flag would force every caller into the coarse behavior; collapsing them into a single
comma-string option would need bespoke parsing/validation this project doesn't otherwise carry
(existing options are plain typer bool/Path/str, see `docs/reference/cli.md`).

The P0 recommendation (§8 open question 2) already settled that this gate should ship opt-in for
2.0, not on-by-default — this change follows that.

## What Changes

- Add `--fail-on-critical` (bool flag, default `False`). When set, the process exits non-zero if the
  rendered 🚨 Critical Changes section is non-empty — i.e. exactly the resources already surfaced
  there (`tier == "critical"` and `action in` that resource's own `critical_on`). Default scope is
  intentionally identical to what the report already renders, so "did the flag fire" never surprises
  someone who only read the report.
- Add `--fail-on-critical-on ACTION` (repeatable; `ACTION` one of `create`, `update`, `delete`,
  `replace`). Passing it one or more times enables the gate — `--fail-on-critical` does not need to
  also be passed — and narrows the trigger to only the given action(s), evaluated against
  `tier == "critical"` resources regardless of each rule's own `critical_on`. This is what answers
  "only fail on delete": `tf-peek plan.json --fail-on-critical-on delete`. It lets a caller be
  stricter at invocation time than the repo's default config without editing `peek_config.toml`. If
  both `--fail-on-critical` and `--fail-on-critical-on` are passed together, the `--fail-on-critical-on`
  scope wins (no error; the combination is harmless and simply narrows the gate).
- Reserve exit code `3` for "the gate fired" — distinct from the existing `1` (runtime error) and `2`
  (usage error), so a CI step can tell "the tool broke" apart from "the plan is risky by design" and
  react differently (e.g. still post the PR comment either way, but only block merge on `3`).
- Neither flag changes report content. The 🚨 section, the summary tables, and everything written to
  stdout or `--output` render identically whether or not either flag is passed — only the process exit
  code changes. This is a deliberate decoupling (see design.md "Decisions" and "Risks"), so a
  `--fail-on-critical-on delete` run can still exit `0` while the report visibly shows a 🚨 replace
  that simply wasn't in scope for this run's gate.
- Update `docs/reference/cli.md`: the two new options, the new exit-code-3 row, and a worked example.

## Capabilities

### Modified Capabilities

- `cli-invocation`: adds the exit-code gate as new, additive requirements on top of the existing
  invocation-shape and `--version` requirements. Nothing existing in this capability changes
  behavior — the delta is purely `## ADDED Requirements`.

### New Capabilities

_None._ The gate reads data the tiering engine (`resource-tier-config`, `critical-section-rendering`)
already computes; it does not add a new domain concept, only a new CLI-surface consumer of an
existing one.

## Impact

- **Code**: `src/tf_peek/main.py` — two new `typer.Option`s on `generate` (`--fail-on-critical`,
  `--fail-on-critical-on` backed by a small action `Enum` for free choice validation), a per-action
  "was a critical-tier resource seen under this action" tally computed alongside the existing
  `critical_resources_by_action`/`tiered_summary` bookkeeping in the same loop, and the gate
  evaluation + `typer.Exit(code=3)` after the report has been written/echoed.
- **Tests**: `tests/test_main.py` — new cases for: default-scope trigger and non-trigger, action-scoped
  trigger and non-trigger (including the "scoped action absent but a *different* critical action is
  present" divergence case), combining both flags, and an invalid `--fail-on-critical-on` value
  producing the existing usage-error exit code (`2`).
- **Docs**: `docs/reference/cli.md` (options table, two new `###` sections, exit-code table, an
  example). No other doc site currently documents exit codes or gating, so no further doc drift risk.
- **No changes** to `resource-tier-config`, `critical-section-rendering`, report templates, or the
  `peek_config.toml` schema — `critical_on` keeps its existing, rendering-only meaning.
