# Architecture Overview

## Purpose

`tf-peek` is a command-line tool that parses Terraform plan JSON files and generates
human-readable Markdown reports. It is designed to make reviewing `terraform plan`
output easier by producing a structured summary with per-resource diffs.

## Core Principles

- **Single responsibility**: one command (`generate`) that performs one task — convert a plan to a report.
- **Offline / local-only**: no network calls, no databases. All processing happens on local files.
- **Declarative configuration**: a TOML file (`peek_config.toml`) controls filtering and summarization per repository.
- **Structured data ingestion**: the Terraform plan JSON is validated at parse time using Pydantic models.
- **Separation of concerns**: parsing, business logic, configuration, and rendering are each
  in their own module.

## Code Organization

```text
src/tf_peek/
├── __init__.py          # Package marker
├── main.py              # CLI definition and orchestration logic
├── models.py            # Pydantic models for the Terraform plan JSON
├── config.py            # Configuration loading (TOML → PeekConfig)
└── templates/
    └── report.md.j2     # Jinja2 template that renders the Markdown report
```

## Processing Pipeline

The `generate` command follows a linear pipeline:

1. **Load configuration** — reads an optional `peek_config.toml` (or a path supplied via `--config`).
2. **Parse plan** — deserializes the Terraform plan JSON into typed Pydantic models.
3. **Filter resources** — resources whose type prefix matches `config.ignore` are skipped entirely;
   resources matching `config.summarize` are included but their attribute diff is hidden.
4. **Classify actions** — each `ResourceChange` is mapped to a simplified action:
   `create`, `update`, `delete`, `replace`, or `no-op`. `no-op` and `read` resources are excluded.
5. **Compute diffs** — for non-summarized resources, before/after attribute values are compared;
   values marked `after_unknown` in the plan are rendered as `(known after apply)`.
6. **Render template** — data is passed to a Jinja2 template that produces the final Markdown.
7. **Output** — the rendered content is written to a file (if `--output` is specified) or printed
   to stdout via `rich`.

## Key Dependencies

| Library    | Role                                                        |
| :--------- | :---------------------------------------------------------- |
| `typer`    | CLI argument parsing and command definition                 |
| `pydantic` | Runtime validation and typing of Terraform plan JSON        |
| `jinja2`   | Markdown report templating                                  |
| `rich`     | Styled terminal output when writing to stdout               |
| `tomllib`  | Standard library TOML parser for reading `peek_config.toml` |
