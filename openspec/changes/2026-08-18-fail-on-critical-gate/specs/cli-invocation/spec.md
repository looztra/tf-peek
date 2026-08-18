## ADDED Requirements

### Requirement: `--fail-on-critical` gates the exit code on the rendered critical section

The system SHALL support a `--fail-on-critical` flag (default off). When present, the system SHALL
exit with status `3` if the 🚨 Critical Changes section would be non-empty (i.e. at least one
resource has `tier == "critical"` and its action is in that resource's own `critical_on` list), and
SHALL exit with status `0` otherwise (absent any other error). The system SHALL NOT change the
rendered report — stdout or the `--output` file — based on this flag; only the exit status changes.

#### Scenario: Flag absent leaves behavior unchanged

- **WHEN** the user runs `tf-peek plan.json` without `--fail-on-critical` or
  `--fail-on-critical-on`, and the plan contains a critical delete
- **THEN** the system renders the report exactly as it does today and exits with status `0`

#### Scenario: Critical operation present triggers the gate

- **WHEN** the user runs `tf-peek plan.json --fail-on-critical`, and the plan contains a resource
  with `tier == "critical"` whose action is in that resource's `critical_on` list
- **THEN** the system writes the report as usual and exits with status `3`

#### Scenario: No critical operation present does not trigger the gate

- **WHEN** the user runs `tf-peek plan.json --fail-on-critical`, and no resource in the plan has
  `tier == "critical"` with an action in its `critical_on` list
- **THEN** the system exits with status `0`

### Requirement: `--fail-on-critical-on` scopes the gate to specific actions

The system SHALL support a repeatable `--fail-on-critical-on ACTION` option, where `ACTION` is one
of `create`, `update`, `delete`, or `replace`. Passing this option one or more times SHALL enable the
gate — independent of whether `--fail-on-critical` is also passed — and SHALL restrict the trigger
condition to: at least one resource has `tier == "critical"` and its action is one of the given
`ACTION` values, evaluated without regard to that resource's own `critical_on` list. On trigger the
system SHALL exit with status `3`; otherwise status `0` (absent any other error). An unrecognized
`ACTION` value SHALL be rejected as a usage error (exit status `2`) before any report generation
begins.

#### Scenario: Scoped to a single action, matching resource present

- **WHEN** the user runs `tf-peek plan.json --fail-on-critical-on delete`, and the plan contains a
  resource with `tier == "critical"` and `simple_action == "delete"`
- **THEN** the system exits with status `3`, regardless of that resource's own `critical_on` value

#### Scenario: Scoped to a single action, only a different critical action present

- **WHEN** the user runs `tf-peek plan.json --fail-on-critical-on delete`, and the plan's only
  `tier == "critical"` resource has `simple_action == "replace"`
- **THEN** the system exits with status `0`, even though the rendered report's 🚨 Critical Changes
  section shows that replace (because `replace` is in that resource's `critical_on`)

#### Scenario: Scoped to multiple actions

- **WHEN** the user runs
  `tf-peek plan.json --fail-on-critical-on delete --fail-on-critical-on replace`, and the plan
  contains a `tier == "critical"` resource with `simple_action == "replace"`
- **THEN** the system exits with status `3`

#### Scenario: Invalid action value is a usage error

- **WHEN** the user runs `tf-peek plan.json --fail-on-critical-on destroy`
- **THEN** the system exits with status `2` and does not generate a report

#### Scenario: Both flags passed together, scoped option wins

- **WHEN** the user runs `tf-peek plan.json --fail-on-critical --fail-on-critical-on delete`, and the
  plan's only `tier == "critical"` resource has `simple_action == "replace"`
- **THEN** the system exits with status `0`, because `--fail-on-critical-on delete` scopes the gate
  and no critical `delete` is present
