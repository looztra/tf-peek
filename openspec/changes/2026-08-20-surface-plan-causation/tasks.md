## 1. Plan model

- [ ] 1.1 Add `Change.replace_paths: list[list[str | int]]` with an empty-list default factory, so a
      plan that omits the field parses to "no forcing paths" rather than `None`
- [ ] 1.2 Add `ResourceChange.action_reason: str | None = None` as an **open** `str` — not a `Literal`
      of the documented codes (design.md, first decision: this field fails open)
- [ ] 1.3 Add an order-sensitive replacement-mechanism property to `ResourceChange` reading
      `change.actions` positionally, leaving the existing membership-based `is_replacement` and
      `simple_action` untouched
- [ ] 1.4 Extend `tests/test_models.py`: both new fields default correctly when absent; the mechanism
      property distinguishes `["delete", "create"]` from `["create", "delete"]`; `simple_action`
      still returns `replace` for both orders

## 2. Causation formatting

- [ ] 2.1 Create `src/tf_peek/causation.py` for path rendering and reason phrasing — separate from
      `formatting.py`, which JSON-serializes and would render a path as a quoted string literal
- [ ] 2.2 Implement path rendering per the notation requirement: numeric step → `[0]`,
      identifier-safe string step → `.tier`, any other string step → a bracketed quoted subscript, no
      separator before the first step
- [ ] 2.3 Sort rendered path strings ascending and de-duplicate them, sorting the **rendered** form
      so the sort key and the displayed text are the same string
- [ ] 2.4 Implement the escaping for the Markdown context (pipe, backtick, CR/LF) and the
      `<summary>` HTML context (additionally `<`, `&`, `"`), and emit the summary short form inside an
      explicit `<code>` element rather than Markdown backticks
- [ ] 2.5 Implement the reason phrasing table for the nine documented codes, mirroring Terraform's own
      vocabulary; an unrecognized code renders behind a "reason reported by Terraform" preamble
- [ ] 2.6 Implement the precedence resolver: forcing paths present → paths only (suppressing
      `replace_because_cannot_update`); paths absent and reason present → phrased reason; neither →
      no explanation
- [ ] 2.7 Implement the unexpected-deletion marker predicate over the four addressing-slip codes,
      excluding `delete_because_no_resource_config`
- [ ] 2.8 Write `tests/test_causation.py` covering 2.2–2.7 as unit tests, including a path whose map
      key carries a pipe, a backtick, a line feed and text resembling an HTML tag

## 3. Configuration

- [ ] 3.1 Add a `ReportOptions` model with `highlight_unexpected_deletes: bool = True` and
      `extra="forbid"`, so a mistyped option key raises instead of silently doing nothing
- [ ] 3.2 Add `PeekConfig.report: ReportOptions` with a default instance, and read the `[report]`
      table in `load_config()` — which currently reads only `resources` and discards every other key
- [ ] 3.3 Extend `tests/test_config.py`: `[report]` present with `false`; `[report]` absent → default
      `true`; `[report]` with an unrecognized key raises; missing config file → default report options

## 4. Report data

- [ ] 4.1 Resolve causation once per resource in `build_report_data()` and add it to `resource_entry`:
      rendered forcing paths, phrased explanation, unexpected-deletion marker state, replacement
      mechanism
- [ ] 4.2 Restructure the `is_summarized` branch so it suppresses attribute value detail only —
      causation is resolved for summarized resources too
- [ ] 4.3 Gate the unexpected-deletion marker on `config.report.highlight_unexpected_deletes`, leaving
      the explanation itself unconditional
- [ ] 4.4 Extend `tests/test_report_rendering.py` for the summarized-and-replaced case: no
      before/after values, forcing path and mechanism present

## 5. Template

- [ ] 5.1 Add the causation short form to the `<summary>` line in both the 🚨 and 🔍 detail blocks,
      bounded with a remainder indicator when it presents fewer paths than the total
- [ ] 5.2 Add the causation callout to the detail-block body: the complete forcing-path list or the
      phrased reason, plus the replacement mechanism for replaced resources
- [ ] 5.3 Render the unexpected-deletion marker on both the summary line and the body callout when
      enabled
- [ ] 5.4 Keep the mechanism statement out of the `<summary>` line (design.md, decision 3C) and keep
      the "Details hidden by configuration" notice for summarized resources' value table

## 6. Fixtures and goldens

- [ ] 6.1 Add focused fixtures under `tests/integration/fixtures/` for each causation case: tainted
      replace with no paths; `replace_by_request` with no paths; paths plus
      `replace_because_cannot_update`; replace with neither paths nor reason; `delete_because_each_key`;
      `delete_because_no_resource_config`; an unrecognized `delete_because_*` code; a
      `["create", "delete"]` replace; duplicate and unsorted paths from one provider
- [ ] 6.2 Add a hostile-path fixture whose forcing path contains a map key holding a pipe, a backtick,
      a line feed and text resembling an HTML tag — required, not optional (design.md, first risk)
- [ ] 6.3 Add a multi-path replace exceeding the `<summary>` bound, to exercise the remainder
      indicator and the complete body list
- [ ] 6.4 Extend `tests/integration/fixtures/kitchen-sink.json` with an `action_reason` and a
      `create_before_destroy` replace so the golden covers both new fields end to end
- [ ] 6.5 Add integration assertions for each 6.1–6.3 fixture, including the `[report]`-disabled
      marker case and the sensitive-attribute forcing-path case
- [ ] 6.6 Regenerate both goldens with `uv run poe pytest:integration --snapshot-update` and review
      the two `.md` diffs line by line — `examples/demo-plan.json:65` and `kitchen-sink.json:49`
      already carry `replace_paths`, so both move
- [ ] 6.7 Confirm `tests/integration/test_defects.py` still passes unchanged: D1–D5 are required
      passing regressions and this change touches the value-rendering path

## 7. Documentation

- [ ] 7.1 Document the `[report]` table and `highlight_unexpected_deletes` in
      `docs/reference/configuration.md`, next to the `[[resources]]` reference
- [ ] 7.2 Add a commented `[report]` example to the root `config.toml`
- [ ] 7.3 Update `docs/explanation/resource-tiers.md` to state that `detail = "summary"` suppresses
      values but keeps causation, which is what makes it a usable middle setting rather than a
      near-`silent`
- [ ] 7.4 Mark P1 1.3 as done in the §7 table of
      `docs/studies/2026-08-15-capability-and-market-analysis.md`, note that `action_reason` shipped
      with it beyond the original recommendation, and update the §4.2 M1 bullet
- [ ] 7.5 Decide design.md's first open question — whether `docs/how-to/` gains a page for "find out
      why Terraform is replacing a resource" — now that the rendering exists and can be shown

## 8. Verification

- [ ] 8.1 Run `uv run poe style`, `uv run poe lint:all` and `uv run poe test`
- [ ] 8.2 Run `pre-commit run --all-files` to cover `markdownlint-cli2` on the changed docs
- [ ] 8.3 Run the determinism check from `deterministic-report-output`: render a plan carrying
      duplicate and unsorted forcing paths in separate processes under differing `PYTHONHASHSEED`
      values and confirm byte-identical output
- [ ] 8.4 Run `openspec validate 2026-08-20-surface-plan-causation --strict`
