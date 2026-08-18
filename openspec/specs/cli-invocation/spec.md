## Purpose

Defines the top-level command-line surface of `tf-peek`: how the tool is invoked to generate a
report, and how a caller can discover which version is installed, independent of report content or
formatting.

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
