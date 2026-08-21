## 1. Plan model

- [x] 1.1 Add `Change.replace_paths: list[list[str | int]]` with an empty-list default factory, so a
      plan that omits the field parses to "no forcing paths" rather than `None`; verify in task 1.4
- [x] 1.2 Add `ResourceChange.action_reason: str | None = None` as an **open** `str`, not a `Literal`
      of known codes; verify absent, known and unknown values in task 1.4
- [x] 1.3 Add an order-sensitive replacement-mechanism property to `ResourceChange` reading
      `change.actions` positionally, leaving the existing membership-based `is_replacement` and
      `simple_action` untouched; verify both replacement orders in task 1.4
- [x] 1.4 Extend `tests/test_models.py`: both new fields default correctly when absent and preserve
      supplied values; the mechanism property distinguishes `["delete", "create"]` from
      `["create", "delete"]`; `simple_action` still returns `replace` for both orders

## 2. Causation formatting

- [x] 2.1 Create `src/tf_peek/causation.py` for path rendering and neutral reason phrasing, separate
      from `formatting.py`, and verify its public behavior through task 2.7
- [x] 2.2 Implement path rendering per the notation requirement: numeric step → `[0]`,
      identifier-safe string step → `.tier`, any other string step → a bracketed quoted subscript,
      with no separator before the first step; verify mixed and hostile paths in task 2.7
- [x] 2.3 Sort rendered path strings ascending and de-duplicate them, sorting the **rendered** form
      so the sort key and displayed text are identical; verify duplicates and input-order changes in
      task 2.7
- [x] 2.4 Implement escaping for the Markdown context (pipe, backtick, CR/LF) and the `<summary>` HTML
      context (additionally `<`, `&`, `"`), emitting the summary short form inside an explicit
      `<code>` element; verify both contexts in task 2.7 and the integration fixture in task 5.2
- [x] 2.5 Phrase the known non-read reason codes emitted by Terraform 1.9.5 in neutral prose,
      including `replace_by_triggers` and `delete_because_no_move_target`; pass an unrecognized code
      through behind a "reason reported by Terraform" preamble; verify every mapping and fallback in
      task 2.7
- [x] 2.6 Implement the narrow precedence resolver: paths plus
      `replace_because_cannot_update` → paths only; paths plus any other recognized or unrecognized
      reason → both; reason without paths → reason; neither → no explanation; verify every branch in
      task 2.7
- [x] 2.7 Write `tests/test_causation.py` covering tasks 2.2–2.6, including neutral deletion wording,
      trigger-driven replacement, unknown reasons with and without paths, and a path whose map key
      carries a pipe, a backtick, a line feed and text resembling an HTML tag

## 3. Report data

- [x] 3.1 Resolve causation once per resource in `build_report_data()` and add rendered forcing
      paths, the neutral reason explanation and replacement mechanism to `resource_entry`; verify
      the rendered data through tasks 3.3 and 5.5
- [x] 3.2 Restructure the `is_summarized` branch so it suppresses attribute value detail only and
      still resolves causation; verify no values and retained causation in task 3.3
- [x] 3.3 Extend `tests/test_report_rendering.py` for a summarized replaced resource: no before/after
      values, forcing path and mechanism present

## 4. Template

- [x] 4.1 Add the causation short form to the `<summary>` line in both the 🚨 and 🔍 detail blocks,
      bounded with a remainder indicator when it presents fewer paths than the total; verify the cap
      and both tier blocks in task 5.5
- [x] 4.2 Add the causation callout to the detail-block body: the complete forcing-path list and any
      non-redundant phrased reason, plus the replacement mechanism for replaced resources; verify
      combined paths and reasons in task 5.5
- [x] 4.3 Keep the mechanism statement out of the `<summary>` line and keep the "Details hidden by
      configuration" notice for summarized resources' value table; verify both placements in tasks
      3.3 and 5.5

## 5. Fixtures and goldens

- [x] 5.1 Add focused fixtures under `tests/integration/fixtures/` for: tainted replacement;
      `replace_by_request`; `replace_by_triggers`; paths plus `replace_because_cannot_update`; paths
      plus an unrecognized non-redundant reason; replacement with neither field; representative
      deletion reasons including `delete_because_no_resource_config`, `delete_because_each_key` and
      `delete_because_no_move_target`; an unrecognized reason; a `["create", "delete"]` replacement;
      and duplicate, unsorted paths; verify each through task 5.5
- [x] 5.2 Add a hostile-path fixture whose forcing path contains a map key holding a pipe, a backtick,
      a line feed and text resembling an HTML tag; verify the generated Markdown and HTML contexts
      remain structurally intact in task 5.5
- [x] 5.3 Add a multi-path replacement exceeding the `<summary>` bound; verify the remainder
      indicator and complete body list in task 5.5
- [x] 5.4 Extend `tests/integration/fixtures/kitchen-sink.json` with an `action_reason` and a
      create-before-destroy replacement so the golden verifies both new fields end to end
- [x] 5.5 Add integration assertions for tasks 5.1–5.4, including neutral reason wording,
      paths-plus-unknown-reason preservation and a sensitive-attribute forcing path
- [x] 5.6 Regenerate both goldens with `uv run poe pytest:integration --snapshot-update` and review
      the two `.md` diffs line by line; `examples/demo-plan.json:65` and `kitchen-sink.json:49`
      already carry `replace_paths`, so both move
- [x] 5.7 Confirm `tests/integration/test_defects.py` still passes unchanged: D1–D5 are required
      passing regressions and this change touches the value-rendering path

## 6. Documentation

- [x] 6.1 Update `docs/explanation/resource-tiers.md` to state that `detail = "summary"` suppresses
      values but keeps causation; verify the rendered docs build
- [x] 6.2 Mark P1 1.3 as done in the §7 table of
      `docs/studies/2026-08-15-capability-and-market-analysis.md`, note that neutral `action_reason`
      rendering shipped beyond the original recommendation, and update the §4.2 M1 bullet; verify
      Markdown links and formatting through the documentation gates

## 7. Verification

- [x] 7.1 Run `uv run poe style`, `uv run poe lint:all` and `uv run poe test`
- [x] 7.2 Run `uvx pre-commit run --all-files` to cover `markdownlint-cli2` on changed docs
- [x] 7.3 Run the determinism check from `deterministic-report-output`: render a plan carrying
      duplicate and unsorted forcing paths in separate processes under differing `PYTHONHASHSEED`
      values and confirm byte-identical output
- [x] 7.4 Run `openspec validate 2026-08-20-surface-plan-causation --strict`
