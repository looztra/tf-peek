# tf-peek Documentation

`tf-peek` is a CLI tool that converts Terraform plan JSON files into human-readable Markdown reports,
with configurable resource tiers for focused review.

This documentation follows the [Diataxis](https://diataxis.fr) framework. Content is organised into
four types based on what you need:

---

## [Tutorial](tutorial/first-report.md) — Learn by doing

Start here if you are new to `tf-peek`.

- [Your first Terraform plan report](tutorial/first-report.md)

---

## [How-to guides](how-to/) — Accomplish a specific task

Step-by-step directions for common tasks. These guides assume you are already familiar with the basics.

- [How to install tf-peek](how-to/install.md)
- [How to generate a Markdown report](how-to/generate-a-report.md)
- [How to silence noisy resource types](how-to/silence-noisy-resources.md)
- [How to flag critical resources](how-to/flag-critical-resources.md)

---

## [Reference](reference/) — Technical facts and specifications

Complete, accurate descriptions of the CLI and configuration format. Use these while working.

- [CLI reference](reference/cli.md)
- [Configuration reference](reference/configuration.md)

---

## [Explanation](explanation/) — Background and concepts

Read these to understand *why* things work the way they do.

- [Resource tiers](explanation/resource-tiers.md)

---

## Architecture

Internal design documentation for contributors:

- [Architecture overview](architecture/01-architecture-overview.md)
- [External services](architecture/02-external-services.md)
- [CLI entry points and data flow](architecture/03-endpoints-and-dependencies.md)
- [Data models](architecture/04-data-models.md)
