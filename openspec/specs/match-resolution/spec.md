## ADDED Requirements

### Requirement: match_pattern takes priority over match_type
When classifying a resource, the system SHALL evaluate all `match_pattern` rules first (in config file order). If no `match_pattern` rule matches, the system SHALL then evaluate `match_type` rules (in config file order). The first matching rule wins. If no rule matches, the resource defaults to `tier = "normal"`, `detail = "full"`.

#### Scenario: match_pattern overrides match_type for same resource
- **WHEN** config has a `match_type = "aiven_pg"` rule with `tier = "normal"` AND a `match_pattern = 'module\\.prod\\..*\\.aiven_pg'` rule with `tier = "critical"`
- **WHEN** a resource has `type = "aiven_pg"` and `address` matching the pattern
- **THEN** the resource is classified as `tier = "critical"` (pattern wins)

#### Scenario: match_type applies when no match_pattern matches
- **WHEN** config has a `match_type = "aiven_pg"` rule with `tier = "critical"`
- **WHEN** a resource has `type = "aiven_pg"` and an address that matches no `match_pattern` rule
- **THEN** the resource is classified as `tier = "critical"` (type rule applies)

#### Scenario: No matching rule defaults to normal/full
- **WHEN** a resource has a type and address that match no configured rule
- **THEN** the resource is classified as `tier = "normal"` and `detail = "full"`

### Requirement: match_type is an exact match on rc.type
The `match_type` value SHALL be compared using exact string equality against `rc.type`. Prefix matching SHALL NOT be used.

#### Scenario: Exact type match
- **WHEN** a rule has `match_type = "aiven_pg"` and a resource has `type = "aiven_pg"`
- **THEN** the rule matches

#### Scenario: Partial type string does not match
- **WHEN** a rule has `match_type = "aiven_p"` and a resource has `type = "aiven_pg"`
- **THEN** the rule does NOT match

### Requirement: match_pattern is a regex applied to rc.address via re.search
The `match_pattern` value SHALL be compiled as a Python regex and evaluated using `re.search()` against the full `rc.address` string. An invalid regex SHALL cause `load_config()` to raise a `ValueError`.

#### Scenario: Pattern matches substring of address
- **WHEN** a rule has `match_pattern = 'aiven_postgresql\[".*-pgsource"\]'`
- **WHEN** a resource has `address = 'module.stack.module.aiven_postgresql["cfurmaniak-sbox-a2cv-pgsource"].aiven_pg.service'`
- **THEN** the rule matches

#### Scenario: Pattern does not match address
- **WHEN** a rule has `match_pattern = 'module\\.prod\\..*\\.aiven_pg'`
- **WHEN** a resource has `address = 'module.staging.aiven_pg.service'`
- **THEN** the rule does NOT match

#### Scenario: Invalid regex raises error at load time
- **WHEN** a rule has `match_pattern = "[unclosed"`
- **THEN** `load_config()` raises a `ValueError` with a message referencing the invalid pattern

### Requirement: First matching rule wins within each strategy
Within `match_pattern` rules and within `match_type` rules, the first rule (by config file order) that matches a resource SHALL be used. Subsequent matching rules SHALL be ignored.

#### Scenario: First match_type rule wins when multiple match
- **WHEN** config has two `match_type = "null_resource"` entries with different tiers
- **WHEN** a resource has `type = "null_resource"`
- **THEN** the resource receives the tier from the first entry
