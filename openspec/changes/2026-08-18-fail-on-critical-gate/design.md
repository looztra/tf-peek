## Context

`generate()` in `src/tf_peek/main.py` already walks every non-`no-op`/`read` resource change once,
resolving its `ResourceRule` via `resolve_tier()` and bucketing it into `critical_resources_by_action`
(used only for the 🚨 section) when `rule.tier == "critical" and action in rule.critical_on`
(`main.py:426`). That bucketing is a *rendering* decision — it decides what shows up under the 🚨
heading, grouped by action then type (`critical-section-rendering` spec). The gate this change adds
is a *process exit-code* decision, and the maintainer's stated requirement — "only fail on delete,
even if the report also shows a critical replace" — means the gate cannot simply reuse
`critical_resources_by_action` as-is once it's scoped: that structure is already filtered by each
rule's own `critical_on`, which is a repo-config-time choice, not an invocation-time one.

## Goals / Non-Goals

**Goals:**
- Ship the gate as strictly additive: no flag passed → identical behavior to today (exit `0` unless
  a genuine runtime/usage error occurs), per the study's P0 open-question-2 recommendation
  (opt-in for 2.0).
- Make the common case ("fail on whatever the report already flags 🚨") a single boolean flag with no
  parsing surface.
- Make the narrow case ("fail only on this action") independent of what any given rule's
  `critical_on` happens to be set to, since the whole point is letting a caller override that at
  invocation time.
- Give CI a way to distinguish "the tool errored" from "the gate fired" via a dedicated exit code.

**Non-Goals:**
- Changing `critical_on`'s meaning or the 🚨 section's contents — both stay exactly as
  `resource-tier-config` and `critical-section-rendering` already specify them.
- A `--fail-on` policy DSL, severity levels, or per-resource-type overrides at the CLI layer — the
  existing `peek_config.toml` tier system is where that kind of policy belongs (§6 of the study is
  explicit that tf-peek's differentiator is the low-ceremony config, not a second policy language).
- Presets / `tf-peek init` (P1 item 1.2) and `replace_paths` surfacing (P1 item 1.3) — separate,
  independent changes.

## Decisions

**Two options, not one comma-string option.** Considered a single `--fail-on-critical[=ACTIONS]`
option accepting an optional comma-separated value (à la `docker build --pull=always`). Rejected:
click/typer's clean way to express "flag alone vs. flag-with-value" needs `is_flag=False` +
`flag_value`, which isn't idiomatic in this codebase's typer usage (every existing option is a plain
bool, `Path`, or eager callback — see `--config`, `--output`, `--show-sensitive`, `--version` in
`main.py`) and would need hand-rolled comma-splitting and validation with a custom error message.
A repeatable `--fail-on-critical-on ACTION` option backed by a `str, Enum` gets per-value validation,
`--help` enumeration of the four legal values, and exit-code-2 usage errors on typos for free from
typer/click — no custom parsing code at all. The plain `--fail-on-critical` bool stays for the
zero-configuration common case so a caller doesn't have to enumerate all four actions just to get
"fail on whatever's critical."

**Default scope (`--fail-on-critical` alone) mirrors the 🚨 section exactly, not a broader
"any critical-tier resource, any action" check.** Alternative considered: default to "any
`tier == critical` resource regardless of action," which would be a stronger gate. Rejected — it
would make the flag fire on a critical `create`, even when the report itself never shows that
resource in the 🚨 section (because `critical_on` defaults to `["delete", "replace"]` and excludes
`create`) — an operator staring at a green-looking report from a job that just failed would have no
visible reason why. Aligning default-scope exactly with `critical_resources_by_action` means "did the
job fail" is always explainable by "is the 🚨 section non-empty," which is the report's whole reason
to exist (§3 of the study — hoisting 🚨 above the fold is called out as the single most important UX
decision).

**Scoped mode (`--fail-on-critical-on`) evaluates `tier == "critical"` independent of each rule's own
`critical_on`.** This is the maintainer's explicit ask: "only fail on delete" must work even for a
critical-tier resource whose `critical_on` is `["replace"]` (i.e. one that would never itself trigger
existing `critical_resources_by_action` bucketing, the scoped gate reads
`tiered_summary[action]["critical"]` — the per-action count of `tier == "critical"` resources,
already accumulated in the same loop unfiltered by `critical_on`. No new data structure: the count
the gate needs is the same one the tiered summary table renders, so there is no second source of
truth to drift out of sync.

**Consequence accepted, not hidden: scoped mode can diverge from the rendered report.** With
`--fail-on-critical-on delete`, a run whose only critical-tier operation is a `replace` (which *does*
render in 🚨, since `replace` is in the default `critical_on`) exits `0`. This is intentional — the
narrow flag is an invocation-time override, not a second renderer — but it is surprising enough to
warrant its own scenario in the spec and its own test, plus an explicit callout in
`docs/reference/cli.md` next to the option's description so nobody discovers it by surprise in CI.

**Exit code `3`, not reusing `1`.** `docs/reference/cli.md` already documents `1` as "Runtime error
(invalid JSON, file not found, configuration error, missing metadata)" — semantically "the tool
couldn't do its job," not "the tool did its job and didn't like what it found." Reusing `1` for the
gate would make `$? -eq 1` in a CI script ambiguous between "fix your JSON path" and "someone's about
to delete a database," which is exactly the kind of alert-fatigue-by-conflation the study's §5.3
market analysis says the whole product thesis is a reaction against. `2` is already reserved for
usage errors (unaffected by this change — an invalid `--fail-on-critical-on` value still produces
`2` via typer's own Enum validation, before the gate logic ever runs). `3` is free.

**Report content and exit code are fully decoupled — no flag ever changes what's rendered.** The
report is generated and written/echoed exactly as it is today; the gate check runs after, purely to
choose the exit code. Mirrors `terraform plan -detailed-exitcode`'s own precedent of separating "what
the plan contains" from "how the caller wants that translated into a shell-level signal" — a familiar
pattern to this tool's actual audience.

**Combining both flags is allowed, not rejected.** `--fail-on-critical-on` always wins when present
(narrows regardless of whether `--fail-on-critical` is also set). Considered making the combination a
usage error to force an explicit choice; rejected as unnecessary ceremony — the combined behavior is
unambiguous and matches what a reasonable reader would expect ("this flag is the specific one, so it
takes precedence").

## Risks / Trade-offs

**[Risk]** A caller reads a 🚨 section, sees a critical replace, and is confused when
`--fail-on-critical-on delete` still exited `0`. → **Mitigation**: documented explicitly in
`docs/reference/cli.md` directly under `--fail-on-critical-on`, and codified as its own spec scenario
(not just an implementation detail) so it's covered by a named test rather than only discoverable by
reading the diff.

**[Risk]** Exit code `3` is a new contract surface; any existing external wrapper script that treats
"non-zero" as one undifferentiated failure bucket won't distinguish it from `1`/`2` today anyway, so
this is additive, not breaking — but a script that specifically branches on `$? -eq 1` to mean
"retry" could now also retry on a `3` it should instead treat as a hard stop. → **Mitigation**: this
is why the exit-code table and worked example in `docs/reference/cli.md` are part of this change, not
deferred; `3` is new API surface that needs to be visible at the same place `1`/`2` already are.

**[Risk]** The four-value action `Enum` (`create`/`update`/`delete`/`replace`) must stay in sync with
`rc.simple_action`'s value set (`models.py`) and `config.py`'s `critical_on` field, which is a plain
`list[str]` with no enum today. → **Mitigation**: the new `Enum`'s member values are string literals
matching `action_order` in `main.py:357`, not re-derived from `config.py` — introducing a shared enum
across `config.py` and `main.py` is a larger refactor (would touch `ResourceRule.critical_on`'s
validation too) and is out of scope here. Two drift guards pin the contract: a test asserting the
`Enum`'s values equal `action_order`, and a second test asserting every `simple_action` outcome that
reaches the tally (create/update/delete/replace) is a selectable `Action` value — so a future
`simple_action` value outside the `Enum` surfaces as a failing test rather than a silent under-gate.

**[Risk — follow-up]** `generate()` carries `# noqa: PLR0913, PLR0917` (the Option A simplification
dropped it below the `C901`/`PLR0915` thresholds this change originally pushed past), and this
change adds two more typer options to it (5 → 7 parameters). Each subsequent flag costs ~12–15
lines across the function, the noqa list, the docs, and the tests — a five-touch diff for a single
boolean. The study's P0 open-question-0.6 already flagged CLI-shape as unresolved. Signal to act
on: a fourth gate or a tenth option ⇒ revisit the CLI shape (extract a `gate` module / subcommand
group) before re-extending `generate()`.

## Migration Plan

Purely additive CLI flags plus a new, previously-unused exit code — no data migration, no change to
existing invocations' behavior or output. Deploy as a normal merge; release-please picks up the
`feat:` commit and infers a minor version bump (or major, if 2.0 is cut first per the study's §8
open question 6 — orthogonal to this change). No rollback concerns beyond a normal revert.
