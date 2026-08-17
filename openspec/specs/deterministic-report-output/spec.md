# deterministic-report-output Specification

## Purpose
Ensures that a report is a reproducible artifact: an unchanged Terraform plan and configuration always yield identical Markdown output, allowing reliable PR-comment updates, diffs, and snapshots.

## Requirements

### Requirement: Report output is reproducible across Python hash seeds
For the same Terraform plan, configuration, and command options, the system SHALL produce byte-identical Markdown output regardless of the Python hash seed used by the rendering process.

#### Scenario: Same plan rendered by separate processes
- **WHEN** separate processes render the same plan with distinct `PYTHONHASHSEED` values
- **THEN** each generated Markdown report is byte-identical

### Requirement: Resource attribute rows have deterministic lexical order
Within each resource details table, changed attributes SHALL appear in ascending lexical order by their property name.

#### Scenario: Plan has attributes in non-lexical source order
- **WHEN** a changed resource has properties whose names are not lexically ordered in the input plan
- **THEN** its report details table lists the changed properties in ascending lexical order

### Requirement: Ordering does not alter report semantics
Making report output deterministic SHALL NOT alter which resource changes, classifications, actions, or attribute differences appear in a report.

#### Scenario: Existing report rendered with deterministic ordering
- **WHEN** an existing plan is rendered after deterministic ordering is introduced
- **THEN** it contains the same resource changes and attribute before/after values as before, except for ordering differences required by this specification
