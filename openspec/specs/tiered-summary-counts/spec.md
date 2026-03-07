## ADDED Requirements

### Requirement: Summary table includes per-tier count columns
The summary table SHALL replace the single `Count` column with four columns: `🚨 Critical`, `Normal`, `🔇 Silent`, and `Total`. Each row corresponds to one action type. A cell SHALL be empty if the count is zero.

#### Scenario: Summary row reflects all tiers
- **WHEN** a plan has 2 critical deletes, 3 normal deletes, and 4 silent deletes
- **THEN** the delete row in the summary table shows: `🚨 Critical = 2`, `Normal = 3`, `🔇 Silent = 4`, `Total = 9`

#### Scenario: Zero counts are empty not zero
- **WHEN** a plan has no critical creates
- **THEN** the 🚨 Critical cell in the create row is empty (not `0`)

#### Scenario: Total Σ row sums all tiers
- **WHEN** the summary table is rendered
- **THEN** the Σ Total row reflects the sum of all tiers across all actions

### Requirement: Critical counts in the summary reflect all critical operations regardless of critical_on
The `🚨 Critical` column SHALL count ALL operations on critical-tier resources (not only those in `critical_on`). The visual separation of which operations appear in the 🚨 section vs. the normal section is a rendering concern, not a counting concern.

#### Scenario: Critical create counted in critical column even if not in critical_on
- **WHEN** a resource has `tier = "critical"` and `critical_on = ["delete", "replace"]`
- **WHEN** the resource has `simple_action = "create"`
- **THEN** the critical create is counted in the 🚨 Critical column of the create row
