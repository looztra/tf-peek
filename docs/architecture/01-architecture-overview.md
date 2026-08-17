# Architecture Overview

## Purpose

`tf-peek` is a command-line tool that parses Terraform plan JSON files and generates
human-readable Markdown reports. It is designed to make reviewing `terraform plan`
output easier by producing a structured summary with per-resource diffs.

## Core Principles

- **Single responsibility**: a single command that performs one task — convert a plan to a report.
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

`tf-peek` follows a linear pipeline:

1. **Load configuration** — reads an optional `peek_config.toml` (or a path supplied via `--config`).
2. **Parse plan** — deserializes the Terraform plan JSON into typed Pydantic models.
3. **Classify actions** — each `ResourceChange` is mapped to a simplified action:
   `create`, `update`, `delete`, `replace`, or `no-op`. `no-op` and `read` resources are excluded.
4. **Classify tier** — each remaining resource is matched against the configured `[[resources]]`
   rules (by exact `match_type` or regex `match_pattern`) and assigned a tier (`silent` / `normal`
   / `critical`) and, for `normal`, a `detail` level (`full` / `summary`). A `critical` resource
   whose action is in that rule's `critical_on` list is routed into the report's 🚨 Critical
   Changes section instead of the normal resource list.
5. **Compute diffs** — `silent`-tier resources and `summary`-detail resources skip diff computation
   entirely (only counted). For the rest, before/after attribute values are compared. Terraform's
   `after_unknown` markers are resolved recursively into the `after` value, so a nested unknown leaf
   becomes `(known after apply)` inside its containing structure instead of being lost.
6. **Mask sensitive values** — an attribute whose `before_sensitive`/`after_sensitive` subtree has any
   truthy leaf is replaced with `(sensitive value)` on both sides, unless `--show-sensitive` is passed.
   Masking runs before any formatting so no serialization path can bypass it.
7. **Format cells** — every remaining value passes through one canonical formatter that emits compact
   JSON and escapes the Markdown table delimiter and the code-span backtick. The template receives
   display strings only, so no branch of it can re-derive a value differently.
8. **Render template** — data is passed to a Jinja2 template that produces the final Markdown.
9. **Output** — the completed Markdown is written to a file (if `--output` is specified) or emitted
   literally to stdout via `typer.echo`. Both destinations pin UTF-8 with LF endings, so their bytes
   are identical regardless of the ambient locale.

## Key Dependencies

| Library    | Role                                                          |
| :--------- | :------------------------------------------------------------ |
| `typer`    | CLI argument parsing, command definition, and literal stdout emission |
| `pydantic` | Runtime validation and typing of Terraform plan JSON          |
| `jinja2`   | Markdown report templating                                    |
| `tomllib`  | Standard library TOML parser for reading `peek_config.toml`   |
