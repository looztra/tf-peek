## Purpose

Defines the top-level command-line surface of `tf-peek`: the preferred `tf-peek` console command,
the supported `python -m tf_peek` module invocation, and how a caller can discover which version is
installed, independent of report content or formatting.

## Requirements

### Requirement: Report generation uses a bare positional invocation

The system SHALL generate a report when invoked as `tf-peek JSON_PATH [OPTIONS]`, with no
subcommand name. The system SHALL NOT require or accept a `generate` subcommand.

#### Scenario: Bare invocation with a plan path

- **WHEN** the user runs `tf-peek plan.json`
- **THEN** the system parses `plan.json` and prints the rendered report

#### Scenario: Legacy `generate` subcommand is rejected

- **WHEN** the user runs `tf-peek generate plan.json`
- **THEN** the system exits non-zero, treating `generate` as an unexpected positional argument
  rather than a recognized subcommand

### Requirement: Module invocation is supported as an alternative

The system SHALL support `python -m tf_peek JSON_PATH [OPTIONS]` with the same CLI behavior and exit
status as `tf-peek JSON_PATH [OPTIONS]`. The `tf-peek` console command SHALL remain the preferred
end-user invocation in documentation and examples.

#### Scenario: Module invocation with a plan path

- **WHEN** the user runs `python -m tf_peek plan.json`
- **THEN** the system parses `plan.json` and prints the rendered report

### Requirement: `--version` reports the installed package version

The system SHALL support a `--version` flag (and its `-V` short form) that prints the installed
`tf-peek` distribution version to stdout and exits with status `0` without requiring a plan path or
performing any report generation.

#### Scenario: Version flag alone

- **WHEN** the user runs `tf-peek --version`
- **THEN** the system prints the installed package version and exits with status `0`, without
  requiring a `JSON_PATH` argument

#### Scenario: Version flag short form

- **WHEN** the user runs `tf-peek -V`
- **THEN** the system behaves identically to `tf-peek --version`

#### Scenario: Distribution metadata is not discoverable

- **WHEN** the user runs `tf-peek --version` and the installed distribution's metadata is not
  discoverable (e.g. running from a source checkout outside an installed venv)
- **THEN** the system writes a one-line diagnostic to stderr, exits with status `1`, and does
  not write anything to stdout. A wrapper doing ``VER=$(tf-peek --version)`` observes the
  non-zero exit and an empty version rather than capturing a prose sentence as a version.

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
