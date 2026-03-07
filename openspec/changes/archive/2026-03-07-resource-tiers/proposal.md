## Why

The current tf-peek report treats all resources uniformly: either fully shown, diff-summarized, or completely ignored (and uncounted). This makes it impossible to distinguish genuinely dangerous operations (deleting a production database) from routine noise (null_resource replacements that always run), forcing users to scan everything to find what truly matters.

## What Changes

- **BREAKING**: Remove `[filters]` section from config (`ignore` and `summarize` keys are gone)
- **BREAKING**: Replace with `[[resources]]` array-of-tables config, each entry assigning a tier and optional attributes to a resource type or address pattern
- Introduce three resource tiers: `silent`, `normal` (default), `critical`
- `silent` resources are counted in summary but never shown in detail — they are disclosed as a 🔇 sub-section in the "Changes by Resource Type" table
- `critical` resources that perform actions listed in `critical_on` (default: `["delete", "replace"]`) are surfaced in a new 🚨 Critical Changes section **above** the main summary — all other actions on critical resources appear in the normal details section
- `normal` resources support an optional `detail = "summary"` property to show title-only collapsed entries (no diff) — replacing the old `summarize` key behaviour
- Summary table gains per-tier breakdown columns: 🚨 Critical | Normal | 🔇 Silent
- Two match strategies: `match_type` (exact match on `rc.type`) and `match_pattern` (regex matched against `rc.address`); `match_pattern` takes priority over `match_type`

## Capabilities

### New Capabilities

- `resource-tier-config`: Configuration schema for assigning tiers and display options to resources via `[[resources]]` TOML array-of-tables, supporting `match_type` and `match_pattern` match strategies
- `critical-section-rendering`: Report section that surfaces critical resource operations above the main summary, with per-operation-type filtering via `critical_on`
- `silent-disclosure`: Silent resources disclosed in the "Changes by Resource Type" table as a 🔇 sub-section, counted but not detailed
- `tiered-summary-counts`: Summary table extended with per-tier columns (🚨 Critical, Normal, 🔇 Silent) per action row

### Modified Capabilities

## Impact

- `src/tf_peek/config.py`: `PeekConfig` model rewritten; `load_config()` parses new `[[resources]]` schema
- `src/tf_peek/models.py`: `ResourceChange` gains a resolved `tier`, `detail`, and `critical_on` after config application
- `src/tf_peek/main.py`: Resource classification logic added; rendering pipeline split to populate critical section and normal section separately; summary stats extended
- `src/tf_peek/templates/report.md.j2`: Template updated for new section order, critical block, silent disclosure in type table, and tiered summary counts
- `config.toml` (sample): Rewritten to use new `[[resources]]` schema
- `tests/`: New tests for config parsing, tier resolution (match precedence), and rendering paths
