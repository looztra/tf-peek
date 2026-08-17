# safe-value-rendering Specification

## Purpose
Ensures every Terraform attribute value can be represented faithfully in a Markdown resource-details table without corrupting report structure or hiding values that are known only after apply.

## Requirements

### Requirement: Scalar values cannot corrupt Markdown table structure
The system SHALL render every scalar diff value as a single physical Markdown table-cell line. Scalar strings SHALL be rendered as JSON string literals so an empty string stays visible and a string `"false"` stays distinct from a boolean `false`. Literal pipe characters SHALL be escaped, backtick characters SHALL be escaped so a value cannot close the code span the cell is wrapped in, and carriage returns and line feeds SHALL be represented without emitting a physical line break in the table row.

#### Scenario: Value contains a pipe and newline
- **WHEN** a changed scalar attribute has an after value containing both `|` and a line feed
- **THEN** its resource-details row remains one physical line
- **THEN** the pipe cannot create an additional Markdown table column
- **THEN** every row in that details table has the same number of cell delimiters

#### Scenario: Scalar string is rendered as a JSON literal
- **WHEN** a changed scalar attribute has an empty string on one side and the text `false` on the other
- **THEN** both cells render as quoted JSON string literals
- **THEN** neither cell is indistinguishable from an absent value or from a boolean

#### Scenario: Value contains a backtick
- **WHEN** a changed value contains a backtick
- **THEN** the rendered cell contains no literal backtick
- **THEN** the cell's code-span wrapper still encloses the whole value

### Requirement: Structured values use JSON representation
The system SHALL render changed dict and list values as valid JSON in resource-details tables rather than Python object representations.

#### Scenario: Nested value contains null
- **WHEN** a changed attribute value is a nested object containing a null value
- **THEN** the rendered cell uses JSON object syntax and the JSON literal `null`
- **THEN** the rendered cell does not use Python single-quoted keys or the `None` literal

#### Scenario: Structured string value contains a pipe and newline
- **WHEN** a non-sensitive changed attribute is a nested structure whose string value contains both `|` and a line feed
- **THEN** its resource-details row remains one physical Markdown table line
- **THEN** the rendered cell parses as JSON and round-trips to the original structured value

### Requirement: Nested unknown values are represented recursively
The system SHALL recursively apply Terraform `after_unknown` markers to nested object and list values before rendering. A `true` marker SHALL render the marked value as `(known after apply) ⏳`, including when the marked object property is absent from the concrete `after` value. A dict or list marker that does not match the corresponding concrete value shape SHALL leave that concrete value unchanged, and a concrete `null` paired with a container marker carrying no `true` leaf SHALL remain a rendered `null` rather than being removed. Resolution SHALL preserve the concrete value's key order and SHALL append only marker-only keys, in sorted order.

#### Scenario: Unknown nested object property is absent from after
- **WHEN** an attribute's `after` value contains `settings.tier` and its nested `after_unknown` marker identifies `settings.ip_address` as true
- **THEN** the rendered `settings` value includes `ip_address` represented as `(known after apply) ⏳`
- **THEN** known properties such as `settings.tier` retain their concrete after values

#### Scenario: Unknown list element
- **WHEN** a nested `after_unknown` marker identifies an element or property within a list as true
- **THEN** that list element or property is represented as `(known after apply) ⏳` in the rendered JSON value

#### Scenario: Marker shape does not match concrete value
- **WHEN** a dict or list `after_unknown` marker is paired with a scalar or a differently shaped concrete value
- **THEN** the rendered value retains that concrete value rather than replacing it with marker-only structure

#### Scenario: Nested null is paired with a container marker
- **WHEN** a nested object property or list element is explicitly `null` and its `after_unknown` marker is an object or list containing no `true` leaf
- **THEN** the rendered value still contains that position as `null`
- **THEN** the report renders successfully

#### Scenario: Concrete key order is preserved
- **WHEN** a changed object attribute carries a nested `after_unknown` marker naming a property absent from the concrete value
- **THEN** the after cell lists the concrete properties in the plan's order, matching the before cell
- **THEN** the marker-only property is appended after them

### Requirement: Rendered content survives each output destination
The system SHALL emit byte-identical report Markdown whether writing to `--output` or the default stdout destination, independently of the ambient locale. Report content SHALL NOT be interpreted as console markup.

#### Scenario: JSON list begins with a lowercase literal
- **WHEN** a rendered structured value begins with a JSON list containing `null`, `true`, or `false`
- **THEN** the complete JSON list appears in stdout output unchanged

#### Scenario: Ambient locale cannot encode the report
- **WHEN** the report is generated twice under an ASCII locale, once to `--output` and once to stdout
- **THEN** both invocations succeed
- **THEN** the file's bytes equal the stdout bytes

### Requirement: Value presentation preserves sensitive-value protection
The system SHALL apply existing sensitive-value masking before value presentation. A sensitivity marker leaf SHALL be treated as sensitive when it is truthy, so an unexpected marker shape fails closed. Presentation formatting SHALL NOT expose a value that the report would otherwise replace with `(sensitive value)`.

#### Scenario: Sensitive structured value contains control characters
- **WHEN** a structured attribute is marked sensitive and contains pipes or line breaks
- **THEN** the report renders `(sensitive value)` instead of serializing any underlying content
