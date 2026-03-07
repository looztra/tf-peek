## ADDED Requirements

### Requirement: Resource rules are defined as a TOML array-of-tables
The configuration file SHALL support a `[[resources]]` array-of-tables where each entry defines how a matched resource is classified and rendered. Each entry SHALL contain exactly one of `match_type` or `match_pattern`, and MAY include `tier`, `detail`, and `critical_on` fields.

#### Scenario: Valid rule with match_type
- **WHEN** a `[[resources]]` entry contains `match_type = "null_resource"` and `tier = "silent"`
- **THEN** `load_config()` returns a rule that classifies all resources with `rc.type == "null_resource"` as `silent`

#### Scenario: Valid rule with match_pattern
- **WHEN** a `[[resources]]` entry contains `match_pattern = 'module\\.prod\\..*\\.aiven_pg'` and `tier = "critical"`
- **THEN** `load_config()` returns a rule that classifies resources whose address matches the pattern as `critical`

#### Scenario: Rule with no match key raises error
- **WHEN** a `[[resources]]` entry contains neither `match_type` nor `match_pattern`
- **THEN** `load_config()` raises a `ValueError` describing the invalid entry

#### Scenario: Rule with both match keys raises error
- **WHEN** a `[[resources]]` entry contains both `match_type` and `match_pattern`
- **THEN** `load_config()` raises a `ValueError` describing the conflict

#### Scenario: Missing config file returns default PeekConfig
- **WHEN** `load_config()` is called with a path that does not exist
- **THEN** it returns a `PeekConfig` with an empty `resources` list

### Requirement: Tier field defaults to "normal"
Each `[[resources]]` entry that omits `tier` SHALL default to `tier = "normal"`.

#### Scenario: Entry without tier key
- **WHEN** a `[[resources]]` entry has `match_type = "some_resource"` and no `tier` field
- **THEN** the parsed rule has `tier = "normal"`

### Requirement: detail field defaults to "full"
Each `[[resources]]` entry that omits `detail` SHALL default to `detail = "full"`. The `detail` field is only meaningful for `tier = "normal"` entries.

#### Scenario: Entry without detail key
- **WHEN** a `[[resources]]` entry has `match_type = "aiven_pg"` and no `detail` field
- **THEN** the parsed rule has `detail = "full"`

### Requirement: critical_on defaults to delete and replace
Each `[[resources]]` entry with `tier = "critical"` that omits `critical_on` SHALL default to `critical_on = ["delete", "replace"]`.

#### Scenario: Critical rule without critical_on
- **WHEN** a `[[resources]]` entry has `tier = "critical"` and no `critical_on` field
- **THEN** the parsed rule has `critical_on = ["delete", "replace"]`

#### Scenario: Critical rule with custom critical_on
- **WHEN** a `[[resources]]` entry has `tier = "critical"` and `critical_on = ["delete", "replace", "update"]`
- **THEN** the parsed rule has `critical_on = ["delete", "replace", "update"]`
