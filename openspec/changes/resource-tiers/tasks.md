## 1. Config Model Rewrite

- [x] 1.1 Define `ResourceRule` Pydantic model with `match_type`, `match_pattern`, `tier`, `detail`, `critical_on` fields and defaults
- [x] 1.2 Add validation to `ResourceRule`: exactly one of `match_type`/`match_pattern` must be set; raise `ValueError` otherwise
- [x] 1.3 Add validation to `ResourceRule`: compile `match_pattern` as a Python regex at parse time; raise `ValueError` on invalid pattern
- [x] 1.4 Rewrite `PeekConfig` to replace `summarize`/`ignore` with `resources: list[ResourceRule]`
- [x] 1.5 Rewrite `load_config()` to parse `[[resources]]` TOML array-of-tables into `PeekConfig`
- [x] 1.6 Update `config.toml` sample file to use new `[[resources]]` schema

## 2. Match Resolution Logic

- [x] 2.1 Implement `resolve_tier(rc: ResourceChange, config: PeekConfig) -> ResourceRule` function applying match priority: `match_pattern` rules first (in order), then `match_type` rules (in order), else default
- [x] 2.2 Write unit tests for `resolve_tier`: exact type match, pattern match, pattern-over-type precedence, first-match-wins, no-match default

## 3. Resource Classification in Main Pipeline

- [x] 3.1 Replace existing `ignore`/`summarize` checks in `generate()` with calls to `resolve_tier()`
- [x] 3.2 Classify each resource into `critical_section`, `normal_section`, or `silent` based on resolved tier and `critical_on`
- [x] 3.3 Build separate `critical_resources_by_action` and `normal_resources_by_action` data structures for template rendering
- [x] 3.4 Compute per-tier summary counts: `counts[action][tier]` where tier is `critical`, `normal`, `silent`

## 4. Template Update

- [x] 4.1 Add 🚨 Critical Changes section at the top of `report.md.j2`, rendered only when critical operations exist, grouped by action → type
- [x] 4.2 Update summary table to render four columns: `🚨 Critical | Normal | 🔇 Silent | Total`; omit zero-count cells
- [x] 4.3 Add 🔇 Silent sub-section to the "Changes by Resource Type" table, listing silent types with per-action counts; omit section when no silent resources
- [x] 4.4 Remove silent resources from the 🔍 Resource Details section
- [x] 4.5 Ensure critical resources whose action is NOT in `critical_on` still appear in 🔍 Resource Details (not the critical section)

## 5. Tests

- [x] 5.1 Add `test_config.py` tests: valid `[[resources]]` parsing, missing match key error, both match keys error, invalid regex error, defaults for tier/detail/critical_on
- [x] 5.2 Add `test_models.py` or `test_config.py` tests for `resolve_tier()` match resolution (all scenarios from spec)
- [x] 5.3 Add `test_main.py` integration tests: silent counts appear in summary but not details, critical delete appears in critical section only, critical create appears in normal section, `detail = "summary"` renders title-only
- [x] 5.4 Add `test_main.py` test: tiered summary counts are correct across all tiers and actions

## 6. Pre-submit

- [x] 6.1 Run `poe lint:all` and fix any issues
- [x] 6.2 Run `poe test` and confirm all tests pass
- [x] 6.3 Generate a sample report from an existing plan file and verify the new sections render correctly
