## ADDED Requirements

### Requirement: Critical operations render in a dedicated top section
The report SHALL include a 🚨 Critical Changes section rendered **before** the summary table, containing only operations on `critical`-tier resources where the action is in the resource's `critical_on` list. If no such operations exist, the section SHALL be omitted entirely.

#### Scenario: Critical delete appears in critical section
- **WHEN** a resource has `tier = "critical"` and `critical_on = ["delete", "replace"]`
- **WHEN** the resource has `simple_action = "delete"`
- **THEN** the resource's detail block appears in the 🚨 Critical Changes section
- **THEN** the resource does NOT appear in the 🔍 Resource Details section

#### Scenario: Critical create does not appear in critical section
- **WHEN** a resource has `tier = "critical"` and `critical_on = ["delete", "replace"]`
- **WHEN** the resource has `simple_action = "create"`
- **THEN** the resource's detail block appears in the 🔍 Resource Details section (not the critical section)

#### Scenario: No critical operations omits the section
- **WHEN** no resource matches a critical tier for an action in its `critical_on` list
- **THEN** the 🚨 Critical Changes section is absent from the rendered report

#### Scenario: critical_on = delete+replace+update surfaces updates
- **WHEN** a resource has `tier = "critical"` and `critical_on = ["delete", "replace", "update"]`
- **WHEN** the resource has `simple_action = "update"`
- **THEN** the resource's detail block appears in the 🚨 Critical Changes section

### Requirement: Critical section groups resources by action then type
Within the 🚨 Critical Changes section, resources SHALL be grouped first by action (delete → replace → update → create, filtered to only actions in `critical_on`), then by resource type, consistent with the ordering in the normal details section.

#### Scenario: Multiple critical resource types under same action
- **WHEN** two critical resources with different types both have `simple_action = "delete"`
- **THEN** they appear under the same ➖ Delete heading in the 🚨 Critical Changes section, each under their respective type sub-heading
