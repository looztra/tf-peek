## ADDED Requirements

### Requirement: Plan JSON can be read from stdin via a `-` sentinel

The system SHALL read the Terraform plan JSON from standard input when `JSON_PATH` is the literal
value `-`, instead of opening a file at that path. The `JSON_PATH` argument SHALL remain required;
omitting it entirely SHALL remain a usage error and SHALL NOT implicitly select stdin.

#### Scenario: Piped plan JSON

- **WHEN** the user runs `terraform show -json plan.tfplan | tf-peek -`
- **THEN** the system reads the plan JSON from stdin and prints the rendered report, identically to
  passing an equivalent file via `JSON_PATH`

#### Scenario: Missing JSON_PATH is still a usage error

- **WHEN** the user runs `tf-peek` with no `JSON_PATH` argument at all
- **THEN** the system exits with status `2` as a usage error and does not read from stdin

#### Scenario: Module invocation supports stdin identically

- **WHEN** the user runs `python -m tf_peek -` with plan JSON piped to stdin
- **THEN** the system behaves identically to `tf-peek -`

### Requirement: Plan input is read as UTF-8 regardless of source

The system SHALL decode the plan JSON as UTF-8 for both file and stdin sources, independent of the
ambient process locale.

#### Scenario: Non-ASCII plan content under a non-UTF-8 locale

- **WHEN** the plan JSON (file or stdin) contains non-ASCII characters and the process locale is not
  UTF-8 (e.g. `LANG=C`)
- **THEN** the system decodes the plan correctly and does not raise a decode error

### Requirement: Unreadable or malformed plan input produces a clean diagnostic

The system SHALL catch plan-loading failures — a missing or unreadable file, undecodable bytes,
malformed JSON, or JSON that does not match the expected Terraform plan structure — and, for each,
write a single-line diagnostic to stderr and exit with status `1`, instead of letting an unhandled
exception (and its traceback) propagate. This SHALL apply identically whether the source is a file
path or stdin.

#### Scenario: Nonexistent file path

- **WHEN** the user runs `tf-peek missing.json` and `missing.json` does not exist
- **THEN** the system writes a one-line diagnostic to stderr, exits with status `1`, and prints no
  traceback

#### Scenario: Malformed JSON

- **WHEN** the plan input (file or stdin) is not syntactically valid JSON
- **THEN** the system writes a one-line diagnostic to stderr, exits with status `1`, and prints no
  traceback

#### Scenario: Syntactically valid JSON that is not a Terraform plan

- **WHEN** the plan input is valid JSON but does not match the Terraform plan structure (e.g.
  missing or wrong-typed required fields)
- **THEN** the system writes a one-line diagnostic to stderr, exits with status `1`, and prints no
  traceback

#### Scenario: Empty stdin

- **WHEN** the user runs `tf-peek -` and stdin is closed immediately with no bytes written
- **THEN** the system treats it as malformed JSON input, writes a one-line diagnostic to stderr, and
  exits with status `1`
