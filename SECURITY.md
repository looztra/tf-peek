# Security policy

## Supported versions

| Version | Supported                                     |
| :------ | :-------------------------------------------- |
| 1.x     | ✅ the latest published release only          |
| < 1.0   | ❌                                             |

Fixes ship as a new release cut from `main`. There are no maintenance branches and no backports.

## Reporting a vulnerability

Report privately through
[GitHub Security Advisories](https://github.com/looztra/tf-peek/security/advisories/new). If that is
unavailable to you, email `christophe.furmaniak@kalaari.net` with `tf-peek security` in the subject.

**Do not open a public issue for a vulnerability.**

Please include:

- the version (`tf-peek --version`) and the exact invocation,
- a redacted plan JSON and `peek_config.toml` that reproduce the behaviour,
- what an attacker gains.

This is a single-maintainer project: expect an acknowledgement within 7 days, best effort, with no
contractual SLA.

## Scope

`tf-peek` reads a Terraform plan JSON from a file or stdin, renders Markdown, and exits. It makes no
network calls, reads no Terraform state, and needs no credentials. The security-relevant surface is
therefore what ends up inside a rendered report — whose primary destination is a durable, indexed,
notification-emailed pull request comment.

In scope:

- **Sensitive value leakage.** Any attribute Terraform marks sensitive (`before_sensitive` /
  `after_sensitive`, at any nesting depth) must render as `(sensitive value)`. A value that reaches
  the report despite being marked sensitive is a vulnerability.
- **Report injection.** Report content that escapes its Markdown table cell, terminates a row, or
  renders as active markup in the destination that consumes the report.
- **Unexpected file system or network access** by the CLI.

Out of scope:

- `--show-sensitive`. It is a documented, explicit opt-out from masking; using it is a decision, not
  a vulnerability.
- Values a plan carries that Terraform does *not* mark sensitive (project ids, hostnames, service
  account names). `tf-peek` renders what the plan declares; silence them with `tier = "silent"` or
  `detail = "summary"`.
- Vulnerabilities in Terraform, in providers, or in the CI system that produces the plan or consumes
  the report.

## Disclosure

Coordinated: fix first, release, then publish a public advisory crediting the reporter unless
anonymity is requested.
