## ADDED Requirements

### Requirement: Silent resources are counted but not shown in details
Resources with `tier = "silent"` SHALL be included in all summary counts (total, per-tier) but SHALL NOT generate any entry in the 🔍 Resource Details section or the 🚨 Critical Changes section.

#### Scenario: Silent resource counted in summary
- **WHEN** a resource has `tier = "silent"` and `simple_action = "create"`
- **THEN** the summary table's `create` row reflects this resource in the 🔇 Silent column
- **THEN** no `<details>` block for this resource appears in the report

### Requirement: Silent resources disclosed in the Changes by Resource Type table
The "Changes by Resource Type" table SHALL include a visually separated 🔇 Silent sub-section listing each silent resource type with its per-action counts. This sub-section SHALL appear after all non-silent resource type rows. If there are no silent resources, the sub-section SHALL be omitted.

#### Scenario: Silent sub-section present when silent resources exist
- **WHEN** two `null_resource` resources are silent, one with `simple_action = "create"` and one with `simple_action = "replace"`
- **THEN** the type table contains a 🔇 Silent sub-section with a `null_resource` row showing 1 replace and 1 create

#### Scenario: Silent sub-section absent when no silent resources
- **WHEN** no resource has `tier = "silent"`
- **THEN** the 🔇 silent sub-section is omitted from the type table

### Requirement: Silent resources from multiple types are each shown on their own row in the silent sub-section
Each distinct silent resource type SHALL have its own row in the 🔇 Silent sub-section of the type table.

#### Scenario: Two silent types get separate rows
- **WHEN** both `null_resource` and `random_id` are configured as `tier = "silent"` and each has changes
- **THEN** the 🔇 Silent sub-section contains two rows: one for `null_resource` and one for `random_id`
