# CLI Reference

`tf-peek` exposes a single command: `generate`.

## Synopsis

```text
tf-peek generate [OPTIONS] JSON_PATH
```

---

## Arguments

| Argument    | Required | Description                                     |
| :---------- | :------: | :---------------------------------------------- |
| `JSON_PATH` |   Yes    | Path to the Terraform plan JSON file to process |

`JSON_PATH` must be a file produced by `terraform show -json <planfile>`.

---

## Options

| Option             | Short | Type | Default            | Description                                                |
| :----------------- | :---: | :--- | :----------------- | :----------------------------------------------------------- |
| `--config PATH`    | `-c`  | Path | `peek_config.toml` | Path to a TOML configuration file                           |
| `--output PATH`    | `-o`  | Path | —                  | Write the Markdown report to this file instead of stdout    |
| `--show-sensitive` |       | Flag | `False`            | Render sensitive attribute values instead of masking them   |
| `--help`           |       |      |                    | Show help message and exit                                  |

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

If `--output` is omitted, the report is printed to stdout via `rich`.

### `--show-sensitive`

By default, `tf-peek` masks any attribute Terraform marks sensitive — replacing its before and
after values with the placeholder `(sensitive value)` in the rendered report. Pass
`--show-sensitive` to disable masking and render the underlying values instead.

Masking is on by default because the report's primary destination is a durable, indexed,
notification-emailed GitHub PR comment. Only pass `--show-sensitive` when that visibility is
acceptable for the run.

---

## Exit codes

| Code | Meaning                                                   |
| ---: | :-------------------------------------------------------- |
|    0 | Success                                                   |
|    1 | Error (invalid JSON, file not found, configuration error) |

---

## Examples

Print report to terminal:

```bash
tf-peek generate plan.json
```

Save report to a file:

```bash
tf-peek generate plan.json --output report.md
```

Use a custom configuration file:

```bash
tf-peek generate plan.json --config infra/peek_config.toml --output report.md
```

---

## See also

- [Configuration reference](configuration.md)
- [How to generate a Markdown report](../how-to/generate-a-report.md)
