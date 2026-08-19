# CLI Reference

`tf-peek` exposes a single top-level command — there is no subcommand name. The installed
`tf-peek` command is the preferred user-facing invocation; `python -m tf_peek` is a supported
alternative when the package is installed but its console script is unavailable on `PATH`.

## Synopsis

Preferred:

```text
tf-peek [OPTIONS] JSON_PATH | -
```

Supported alternative:

```text
python -m tf_peek [OPTIONS] JSON_PATH | -
```

---

## Arguments

| Argument    | Required | Description                                                    |
| :---------- | :------: | :--------------------------------------------------------------- |
| `JSON_PATH` |   Yes    | Path to the Terraform plan JSON file to process, or `-` to read it from stdin |

`JSON_PATH` must be a file produced by `terraform show -json <planfile>` — or that same output
piped to stdin when `JSON_PATH` is `-`. `JSON_PATH` is always required; omitting it entirely is a
usage error (exit `2`), even though `-` is accepted as its value. There is no way to name a real
file literally called `-`; use a path like `./-` instead.

---

## Options

| Option                       | Short | Type   | Default            | Description                                                       |
| :--------------------------- | :---: | :----- | :----------------- | :------------------------------------------------------------------ |
| `--config PATH`              | `-c`  | Path   | `peek_config.toml` | Path to a TOML configuration file                                 |
| `--output PATH`              | `-o`  | Path   | —                  | Write the Markdown report to this file instead of stdout          |
| `--show-sensitive`           |       | Flag   | `False`            | Render sensitive attribute values instead of masking them         |
| `--fail-on-critical`         |       | Flag   | `False`            | Exit `3` if the rendered 🚨 Critical Changes section is non-empty |
| `--fail-on-critical-on ACTION` |     | Choice (repeatable) | —      | Exit `3` if a critical-tier resource has this action               |
| `--version`                  | `-V`  | Flag   | `False`            | Print the installed `tf-peek` version and exit                    |
| `--help`                     |       |        |                    | Show help message and exit                                        |

### `--config / -c`

Specifies the path to a `peek_config.toml` configuration file.

If this option is omitted, `tf-peek` looks for `peek_config.toml` in the current working directory.
If that file does not exist either, `tf-peek` proceeds with an empty configuration: all resources are
classified as `normal` with `detail = "full"`.

### `--output / -o`

Writes the rendered Markdown to the specified file.

If the file already exists it is overwritten. `tf-peek` prints a notice to stdout:

```text
Overwriting <path>
Report written to <path>
```

If `--output` is omitted, the completed Markdown report is emitted literally to stdout.

### `--show-sensitive`

By default, `tf-peek` masks any attribute Terraform marks sensitive — replacing its before and
after values with the placeholder `(sensitive value)` in the rendered report. Pass
`--show-sensitive` to disable masking and render the underlying values instead.

Masking is on by default because the report's primary destination is a durable, indexed,
notification-emailed GitHub PR comment. Only pass `--show-sensitive` when that visibility is
acceptable for the run.

### `--fail-on-critical`

When set, `tf-peek` exits with status `3` if the rendered 🚨 Critical Changes section is
non-empty — i.e. at least one resource has `tier == "critical"` and its action is in that
resource's own `critical_on` list. Default scope is intentionally identical to what the report
already renders: whether the flag fired is always explainable by whether the 🚨 section is
non-empty. Neither the report written to stdout nor the one written to `--output` is affected —
only the exit status changes.

### `--fail-on-critical-on ACTION`

A repeatable option (`ACTION` is one of `create`, `update`, `delete`, `replace`). Passing it one
or more times enables the gate on its own — `--fail-on-critical` does not also need to be passed
— and narrows the trigger to only the given action(s), evaluated against `tier == "critical"`
resources regardless of each resource's own `critical_on`. This lets a caller be stricter at
invocation time than the repo's `peek_config.toml` without editing it, e.g.
`--fail-on-critical-on delete` to fail CI only when something is being deleted.

If both `--fail-on-critical` and `--fail-on-critical-on` are passed together,
`--fail-on-critical-on`'s narrower scope wins.

An unrecognized `ACTION` value is rejected as a usage error (exit `2`) before any report
generation begins.

**This can diverge from what the 🚨 section shows.** Because `--fail-on-critical-on` ignores each
resource's own `critical_on`, a run can exit `0` even while the rendered report visibly shows a
🚨 change of a different action — e.g. `--fail-on-critical-on delete` exits `0` on a plan whose
only critical-tier operation is a `replace` (which does render in 🚨, since `replace` is in the
default `critical_on`). The flag is an invocation-time override of the gate, not a second
renderer of the report.

### `--version / -V`

Prints the installed `tf-peek` distribution version to stdout and exits `0`. This is an eager
flag: it takes effect before `JSON_PATH` is validated, so `tf-peek --version` works without
supplying a plan file.

If the distribution's metadata is not discoverable (e.g. running from a source checkout outside
an installed venv), `tf-peek --version` writes a one-line diagnostic to stderr and exits `1`
instead of emitting a non-version string to stdout. A wrapper doing `VER=$(tf-peek --version)`
observes the non-zero exit and an empty `VER` rather than capturing prose as a version.

---

## Exit codes

| Code | Meaning                                                                                  |
| ---: | :--------------------------------------------------------------------------------------- |
|    0 | Success                                                                                  |
|    1 | Runtime error (unreadable/missing plan input, malformed or structurally invalid plan JSON, configuration error, missing metadata) — deliberate and tested for both file and stdin plan sources |
|    2 | Usage error (missing or unexpected arguments, unknown option, malformed positional input) |
|    3 | Critical gate triggered (`--fail-on-critical`/`--fail-on-critical-on`); the report was still generated |

---

## Examples

Print report to terminal:

```bash
tf-peek plan.json
```

Read the plan JSON from stdin instead of a file:

```bash
terraform show -json plan.tfplan | tf-peek -
```

Save report to a file:

```bash
tf-peek plan.json --output report.md
```

Use a custom configuration file:

```bash
tf-peek plan.json --config infra/peek_config.toml --output report.md
```

Print the installed version:

```bash
tf-peek --version
```

Gate a CI step on only critical deletes, tolerating other critical changes:

```bash
tf-peek plan.json --fail-on-critical-on delete --output report.md
```

In the CI step, branch on exit code `3` (gate fired — block merge) separately from `1` (the tool
errored — a different failure mode entirely):

```bash
tf-peek plan.json --fail-on-critical-on delete --output report.md
status=$?
if [ "$status" -eq 3 ]; then
  echo "Critical delete detected — blocking merge"
  exit 1
elif [ "$status" -ne 0 ]; then
  echo "tf-peek failed to run (exit $status)"
  exit "$status"
fi
```

---

## See also

- [Configuration reference](configuration.md)
- [How to generate a Markdown report](../how-to/generate-a-report.md)
