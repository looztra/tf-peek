## Why

`tf-peek` reports Terraform values directly inside Markdown table cells. Values containing pipes or newlines corrupt the report, nested values appear as Python representations instead of JSON, and nested `after_unknown` markers are omitted. A report intended for CI and pull-request review must remain structurally valid and faithfully communicate unknown values for every valid Terraform plan.

## What Changes

- Add a canonical report-value presentation contract for values rendered in resource-details tables.
- Render structured Terraform values as JSON rather than Python representations.
- Normalize line breaks and escape Markdown table delimiters so scalar values cannot corrupt table structure.
- Recursively apply nested `after_unknown` markers so unknown leaves are rendered as known-after-apply values within their containing structure.
- Preserve default sensitive-value masking before value presentation; `--show-sensitive` continues to opt out of masking.
- Convert the existing D3, D4, and D5 integration regressions from strict expected failures into passing behavioral coverage.

## Capabilities

### New Capabilities
- `safe-value-rendering`: Renders arbitrary Terraform attribute values safely and faithfully in Markdown resource-details tables, including structured and nested-unknown values.

### Modified Capabilities
- None.

## Impact

- Affected code: `src/tf_peek/main.py`, report value rendering supplied to `src/tf_peek/templates/report.md.j2`, and typed plan handling if needed for nested unknown markers.
- Affected tests: `tests/integration/test_defects.py`, its fixtures, and the report golden coverage.
- Public behavior: Markdown representation of non-sensitive values changes to safe JSON-oriented table cells; no new CLI options, dependencies, network access, or state access.
