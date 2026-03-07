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

| Option          | Short | Type | Default            | Description                                              |
| :-------------- | :---: | :--- | :----------------- | :------------------------------------------------------- |
| `--config PATH` | `-c`  | Path | `peek_config.toml` | Path to a TOML configuration file                        |
| `--output PATH` | `-o`  | Path | —                  | Write the Markdown report to this file instead of stdout |
| `--help`        |       |      |                    | Show help message and exit                               |

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
