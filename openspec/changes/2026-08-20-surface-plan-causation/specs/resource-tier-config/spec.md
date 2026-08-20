## ADDED Requirements

### Requirement: Report presentation options are defined in a `[report]` table

The configuration file SHALL support an optional top-level `[report]` table holding options that affect report presentation rather than the classification of an individual resource. The table MAY include `highlight_unexpected_deletes`. An unrecognized key inside `[report]` SHALL be rejected rather than ignored, because an option that silently does nothing is indistinguishable from an option that is not honoured.

#### Scenario: Config sets a report option

- **WHEN** the configuration file contains a `[report]` table with `highlight_unexpected_deletes = false`
- **THEN** `load_config()` returns a config whose report options disable the unexpected-deletion marker

#### Scenario: Config omits the report table

- **WHEN** the configuration file contains only `[[resources]]` entries and no `[report]` table
- **THEN** `load_config()` returns a config whose report options all take their default values

#### Scenario: Report table contains an unrecognized key

- **WHEN** the configuration file contains a `[report]` table with a key that is not a defined report option
- **THEN** `load_config()` raises a `ValueError` naming the unrecognized key

#### Scenario: Missing config file yields default report options

- **WHEN** `load_config()` is called with a path that does not exist
- **THEN** it returns a config whose report options all take their default values

### Requirement: highlight_unexpected_deletes defaults to true

A `[report]` table that omits `highlight_unexpected_deletes` SHALL default to `highlight_unexpected_deletes = true`. The option exists to be switched off by a repository that finds the marker noisy; its value comes from being present before anyone knew to ask for it, so the default is on.

#### Scenario: Report table omits the key

- **WHEN** the configuration file contains a `[report]` table that does not set `highlight_unexpected_deletes`
- **THEN** the parsed report options have `highlight_unexpected_deletes = true`
