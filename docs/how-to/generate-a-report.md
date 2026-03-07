# How to Generate a Markdown Report

This guide shows you how to generate a Markdown report from a Terraform plan JSON file.

## Prerequisites

- `tf-peek` installed (see [How to install tf-peek](install.md))
- A Terraform plan exported to JSON

---

## Produce the Terraform plan JSON

If you have not already exported your plan to JSON, do it now:

```bash
terraform plan -out=tfplan
terraform show -json tfplan > plan.json
```

---

## Generate and print to stdout

Pass the JSON file as the positional argument to `tf-peek generate`:

```bash
tf-peek generate plan.json
```

The Markdown report is printed to stdout. You can pipe it to any tool that accepts Markdown.

---

## Save to a file

To write the report to a file instead of printing it, use `--output` (short form: `-o`):

```bash
tf-peek generate plan.json --output report.md
```

If the file already exists, `tf-peek` will overwrite it and print a notice:

```text
Overwriting report.md
Report written to report.md
```

---

## Use a custom configuration file

By default `tf-peek` looks for `peek_config.toml` in the current working directory.
To point it at a different file, use `--config` (short form: `-c`):

```bash
tf-peek generate plan.json --config path/to/my-config.toml
```

If neither the default file nor the specified file exists, `tf-peek` proceeds with an empty
configuration (all resources are classified as `normal`).

---

## Combine options

Options can be combined freely:

```bash
tf-peek generate plan.json \
  --config infra/peek_config.toml \
  --output reports/$(date +%Y%m%d).md
```

---

## See also

- [CLI reference](../reference/cli.md) — complete argument and option descriptions
- [How to silence noisy resource types](silence-noisy-resources.md)
- [How to flag critical resources](flag-critical-resources.md)
