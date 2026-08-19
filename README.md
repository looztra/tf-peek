# tf-peek

[![PyPI version](https://img.shields.io/pypi/v/tf-peek)](https://pypi.org/project/tf-peek/)
[![Python versions](https://img.shields.io/pypi/pyversions/tf-peek)](https://pypi.org/project/tf-peek/)
[![Code checks](https://github.com/looztra/tf-peek/actions/workflows/code-checks.yaml/badge.svg)](https://github.com/looztra/tf-peek/actions/workflows/code-checks.yaml)
[![License](https://img.shields.io/pypi/l/tf-peek)](https://github.com/looztra/tf-peek/blob/main/LICENSE)
[![Documentation](https://img.shields.io/badge/docs-looztra.github.io%2Ftf--peek-blue)](https://looztra.github.io/tf-peek/)

**The Terraform plan reviewer that knows what your team considers dangerous.**

Declare your risk model once in `peek_config.toml`. Get a Markdown review report that escalates what
matters, silences what doesn't, and fails the build when something irreversible is on the table.

![Two report panels side by side: without a risk model every one of 12 changes looks the same, with a peek_config.toml three critical changes are hoisted into a 🚨 section above the summary and four routine changes are counted as silent.](https://raw.githubusercontent.com/looztra/tf-peek/main/docs/assets/report-before-after.png)

Same plan, same command, one `peek_config.toml` apart. On the left, 12 changes all look alike and the
replaced production database is somewhere below the fold. On the right, 3 critical operations are
hoisted above the summary and 4 routine changes are counted but not detailed.

## Why tf-peek

Every other plan renderer shows you *what* changes. `tf-peek` renders *an opinion about* the plan.

- **Three tiers, declared per repository** — `silent`, `normal`, `critical`, matched on resource type
  or on an address regex. No policy DSL, no Rego, no SaaS.
- **Per-action escalation** — `critical_on = ["delete", "replace"]`: creating a bucket is routine,
  deleting one is not.
- **🚨 above the fold** — critical changes render *before* the summary, so a destructive operation
  survives a skim of a 400-line report.
- **Silenced, never hidden** — silent resources are still counted, so the report never lies by
  omission.
- **Sensitive values masked by default** — anything Terraform marks sensitive renders as
  `(sensitive value)` at any nesting depth; `--show-sensitive` is an explicit opt-out.
- **A gate, not just a report** — `--fail-on-critical` exits `3` when a critical operation is on the
  table, so CI can block the merge.
- **Deterministic and offline** — same plan in, byte-identical report out. No network calls, no state
  access, no credentials. Safe to run in any pipeline.

## Install

```bash
uv tool install tf-peek   # or: pipx install tf-peek   or: pip install tf-peek
```

## Quick start

```bash
terraform plan -out=tfplan
terraform show -json tfplan > plan.json
tf-peek plan.json --output report.md
```

Or pipe the plan straight in:

```bash
terraform show -json tfplan | tf-peek -
```

## Declare your risk model

`tf-peek` reads `peek_config.toml` from the current working directory, or the file given to
`--config`:

```toml
# Counted in the summary, never detailed.
[[resources]]
match_type = "null_resource"
tier = "silent"

# Deleting or replacing this is a 🚨 event — and so is updating it.
[[resources]]
match_type = "google_sql_database_instance"
tier = "critical"
critical_on = ["delete", "replace", "update"]

# Noisy but harmless: title only, no attribute diff.
[[resources]]
match_type = "google_project_iam_member"
tier = "normal"
detail = "summary"
```

Without a config file every resource is `normal` — that is the left-hand side of the screenshot
above. The full GCP-flavoured example used for the right-hand side is
[`config.toml`](https://github.com/looztra/tf-peek/blob/main/config.toml), and the plan it was run
against is [`examples/demo-plan.json`](https://github.com/looztra/tf-peek/blob/main/examples/demo-plan.json).

## Gate CI on critical changes

```bash
tf-peek plan.json --fail-on-critical --output report.md
status=$?
if [ "$status" -eq 3 ]; then
  echo "Critical change detected — blocking merge"
  exit 1
elif [ "$status" -ne 0 ]; then
  echo "tf-peek failed to run (exit $status)"
  exit "$status"
fi
```

Exit `3` means the gate fired and the report was still written; exit `1` means the tool itself
failed. Use `--fail-on-critical-on delete` to fail only on destructive actions.

## Documentation

Full documentation lives at [looztra.github.io/tf-peek](https://looztra.github.io/tf-peek/),
organised with the [Diataxis](https://diataxis.fr) framework:

| Type        | Start here                                                                                                                                                                                                                                                                        |
| :---------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tutorial    | [Your first Terraform plan report](https://looztra.github.io/tf-peek/tutorial/first-report/)                                                                                                                                                                                       |
| How-to      | [Install](https://looztra.github.io/tf-peek/how-to/install/) · [Generate a report](https://looztra.github.io/tf-peek/how-to/generate-a-report/) · [Silence noisy resources](https://looztra.github.io/tf-peek/how-to/silence-noisy-resources/) · [Flag critical resources](https://looztra.github.io/tf-peek/how-to/flag-critical-resources/) |
| Reference   | [CLI](https://looztra.github.io/tf-peek/reference/cli/) · [Configuration](https://looztra.github.io/tf-peek/reference/configuration/)                                                                                                                                              |
| Explanation | [Resource tiers](https://looztra.github.io/tf-peek/explanation/resource-tiers/)                                                                                                                                                                                                    |

## Contributing

Issues and pull requests are welcome — see
[CONTRIBUTING.md](https://github.com/looztra/tf-peek/blob/main/CONTRIBUTING.md) and the
[Code of Conduct](https://github.com/looztra/tf-peek/blob/main/CODE_OF_CONDUCT.md). Curated tier
presets for a provider you know well are the highest-value contribution and need domain knowledge
rather than Python.

To report a vulnerability, follow the
[security policy](https://github.com/looztra/tf-peek/blob/main/SECURITY.md) — never a public issue.

## License

[Apache-2.0](https://github.com/looztra/tf-peek/blob/main/LICENSE)
