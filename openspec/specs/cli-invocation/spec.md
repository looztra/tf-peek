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
