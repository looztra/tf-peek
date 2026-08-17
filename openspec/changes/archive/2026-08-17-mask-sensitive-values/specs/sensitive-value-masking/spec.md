## Purpose

Prevents Terraform-marked-sensitive attribute values (passwords, keys, connection strings) from
appearing in plaintext in the rendered report, since the report's primary destination is a durable,
indexed, notification-emailed GitHub PR comment visible to anyone with repo read access.

## ADDED Requirements

### Requirement: Sensitive attributes are masked by default
The system SHALL replace the before and after values of any attribute Terraform marks sensitive
with the literal placeholder `(sensitive value)`, rather than rendering the underlying value, in
every resource-details table the report produces.

#### Scenario: Attribute sensitive in both before and after
- **WHEN** a resource's `before_sensitive` and `after_sensitive` both mark attribute `password` as
  sensitive
- **THEN** the report renders `(sensitive value)` for both the before and after cells of `password`
  and never renders the underlying plaintext

#### Scenario: Attribute sensitive on only one side
- **WHEN** an attribute is marked sensitive in `after_sensitive` but not in `before_sensitive` (or
  vice versa)
- **THEN** the report renders `(sensitive value)` for that attribute's before and after cells

### Requirement: Nested sensitivity masks the entire value conservatively
Terraform may mark sensitivity on a nested attribute using a `dict` or `list` shape mirroring the
value's structure, rather than a flat `bool`. Since nested values are rendered as a single blob
(no path-level diffing), the system SHALL mask the entire top-level attribute value whenever any
sensitivity marker within its subtree is truthy, rather than only the specific nested leaf.

#### Scenario: Sensitivity nested inside a block attribute
- **WHEN** a resource has a `settings` attribute whose `before_sensitive`/`after_sensitive` marker
  is a nested structure with a truthy value at any depth (e.g. `settings.credentials.password`)
- **THEN** the report renders `(sensitive value)` for the entire `settings` attribute, not only the
  nested sensitive leaf

### Requirement: Masking can be explicitly disabled
The system SHALL provide a `--show-sensitive` CLI flag that disables masking and renders
underlying values as it would for any other attribute. Masking SHALL be the default behavior when
the flag is not passed.

#### Scenario: Operator opts out of masking
- **WHEN** the CLI is invoked with `--show-sensitive`
- **THEN** sensitive attribute values render as their underlying before/after values instead of
  `(sensitive value)`

#### Scenario: Default invocation masks
- **WHEN** the CLI is invoked without `--show-sensitive`
- **THEN** sensitive attribute values render as `(sensitive value)`
