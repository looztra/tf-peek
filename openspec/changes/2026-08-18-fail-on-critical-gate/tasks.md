## 1. Gate implementation

- [x] 1.1 In `src/tf_peek/main.py`, add a string `Enum` (e.g. `Action`) with members
      `create`/`update`/`delete`/`replace`, values matching `action_order` (`main.py:357`). Add a
      test asserting the enum's values equal `action_order` verbatim, so the two can't silently
      drift (see design.md "Risks").
- [x] 1.2 Add `fail_on_critical: bool = typer.Option(False, "--fail-on-critical", help=...)` and
      `fail_on_critical_on: list[Action] = typer.Option([], "--fail-on-critical-on", help=...)` to
      `generate()`.
- [x] 1.3 In the existing per-resource loop in `generate()` (around `main.py:380-429`), alongside
      the existing `critical_resources_by_action` bucketing, tally
      `critical_tier_actions_seen: set[str]` — add `action` whenever `rule.tier == "critical"`,
      unconditional on `action in rule.critical_on`. One `set.add()`, no second pass over
      `plan.resource_changes`.
- [x] 1.4 After the report is rendered and written/echoed (after the existing `if output_file: ...
      else: ...` block), evaluate the gate:
      - If `fail_on_critical_on` is non-empty: trigger iff any of its values is in
        `critical_tier_actions_seen`.
      - Else if `fail_on_critical` is set: trigger iff `critical_resources_by_action` is non-empty
        (any action key present).
      - Else: never trigger.
      - On trigger, `raise typer.Exit(code=3)`.
- [x] 1.5 Confirm (existing typer/click behavior, no new code) that an invalid
      `--fail-on-critical-on` value exits `2` before `json_path` is opened — add a regression test
      rather than hand-rolled validation.

## 2. Tests (`tests/test_main.py`)

- [x] 2.1 `test_fail_on_critical_absent_exits_zero` — plan with a critical delete, no flags passed,
      asserts `exit_code == 0` and report content unchanged from today's golden output.
- [x] 2.2 `test_fail_on_critical_triggers_on_default_scope` — plan with a resource whose
      `tier == "critical"` and action in its own `critical_on`, `--fail-on-critical` passed, asserts
      `exit_code == 3` and that the report was still written/echoed in full.
- [x] 2.3 `test_fail_on_critical_no_critical_resources_exits_zero` — `--fail-on-critical` passed, no
      `tier == "critical"` resources in the plan, asserts `exit_code == 0`.
- [x] 2.4 `test_fail_on_critical_on_scoped_action_present` — `--fail-on-critical-on delete`, a
      critical-tier resource with `simple_action == "delete"` whose own `critical_on` is `["replace"]`
      only (i.e. would NOT appear in the 🚨 section), asserts `exit_code == 3` — this is the
      maintainer's originating "only fail on delete" scenario and must not go through
      `critical_resources_by_action`.
- [x] 2.5 `test_fail_on_critical_on_divergence_from_rendered_section` — `--fail-on-critical-on
      delete`, plan's only critical-tier resource is a `replace` (renders in 🚨 by default
      `critical_on`), asserts `exit_code == 0` AND that the rendered output still contains the 🚨
      heading — locks in the documented report/gate decoupling from design.md.
- [x] 2.6 `test_fail_on_critical_on_multiple_actions` — two `--fail-on-critical-on` occurrences,
      asserts a resource matching either triggers `exit_code == 3`.
- [x] 2.7 `test_fail_on_critical_on_invalid_action_is_usage_error` — `--fail-on-critical-on destroy`,
      asserts `exit_code == 2` and no report is written even if `--output` was also passed.
- [x] 2.8 `test_fail_on_critical_on_takes_precedence_when_both_flags_passed` — both
      `--fail-on-critical` and `--fail-on-critical-on delete` passed, only a critical replace present,
      asserts `exit_code == 0`.

## 3. Documentation

- [x] 3.1 `docs/reference/cli.md`: add `--fail-on-critical` and `--fail-on-critical-on ACTION` rows
      to the options table, with a `###` subsection each (mirroring the existing `--show-sensitive`
      and `--version` subsections), including the explicit divergence-from-🚨-section callout for
      `--fail-on-critical-on`.
- [x] 3.2 `docs/reference/cli.md`: add exit code `3` to the exit-codes table
      ("Critical gate triggered (`--fail-on-critical`/`--fail-on-critical-on`); the report was still
      generated").
- [x] 3.3 `docs/reference/cli.md`: add a worked example, e.g.
      `tf-peek plan.json --fail-on-critical-on delete` in a CI step, with a one-line note on
      branching on exit code `3` vs `1`.

## 4. Verification

- [x] 4.1 Run `poe lint:all`.
- [x] 4.2 Run `poe test` (full suite, including the new gate tests).
- [x] 4.3 Manually run `tf-peek --fail-on-critical-on delete` and `--fail-on-critical-on destroy`
      against a sample plan to confirm exit codes `3`/`0`/`2` match the spec scenarios.
- [x] 4.4 Run `pre-commit run --all-files markdownlint-cli2` (docs lint clean).
