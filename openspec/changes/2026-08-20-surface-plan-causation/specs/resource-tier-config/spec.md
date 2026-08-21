## MODIFIED Requirements

### Requirement: detail field defaults to "full"

Each `[[resources]]` entry that omits `detail` SHALL default to `detail = "full"`. The `detail` field is only meaningful for `tier = "normal"` entries. `detail = "summary"` SHALL suppress attribute *values* only: a summarized resource SHALL render no before/after value, and SHALL still render the plan metadata explaining its change — the forcing paths, the stated reason and the replacement mechanism owned by `plan-causation-rendering`. The in-report notice SHALL say that attribute values are hidden, so it does not contradict the metadata rendered beside it.

#### Scenario: Entry without detail key

- **WHEN** a `[[resources]]` entry has `match_type = "mukta_pg"` and no `detail` field
- **THEN** the parsed rule has `detail = "full"`

#### Scenario: Summarized resource hides values but not the explanation

- **WHEN** a resource matched by a rule with `detail = "summary"` is being replaced and states a forcing path
- **THEN** its detail block presents no attribute before/after values
- **THEN** its detail block presents the forcing path and the replacement mechanism
- **THEN** the notice states that attribute values are hidden rather than that details are hidden
