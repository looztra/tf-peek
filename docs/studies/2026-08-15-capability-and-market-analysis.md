# tf-peek — Capability & Market Analysis

**Date**: 2026-08-15
**Scope**: repository state at commit `508e5f8`, version `1.0.0`
**Stated ambition**: serious OSS contender · provider-agnostic core with GCP-first presets ·
GitHub PR comment + local CLI + HTML reports

---

## 1. Executive summary

`tf-peek` has a genuinely good idea that no competitor implements: **a declarative, per-repository
risk classification of Terraform resources** (`silent` / `normal` / `critical`, plus `critical_on`
per-action escalation). Everyone else in this space renders the plan; `tf-peek` renders *an opinion
about* the plan. That is the differentiator, and it is defensible.

The idea is currently wrapped in an implementation that is **not yet safe to point at a real plan in
CI**. Five defects found by running the tool against a realistic plan fragment (§4.1) range from
cosmetic to disqualifying, the worst being **plaintext leakage of values Terraform explicitly marked
sensitive**. For a tool whose headline use case is "post this into a pull request comment", that is a
release blocker, not a backlog item.

The recommendation is therefore sequenced, not balanced:

| Phase | Theme | Why |
| :--- | :--- | :--- |
| **P0** | Correctness & safety | The current output is unsafe and non-reproducible. Nothing else matters until this is fixed. |
| **P1** | Lean into the differentiator | Ship presets, a risk gate exit code, and `replace_paths`. This is the moat. |
| **P2** | Reach | GitHub Action, HTML renderer, stdin. This is how people find it. |

Estimated effort to a credible 2.0: **P0 ≈ 2–3 focused days, P1 ≈ 4–5 days, P2 ≈ 4–5 days.** The
codebase is 336 lines of source with 35 passing tests, so the surface area is small and the work is
tractable.

---

## 2. What tf-peek is today

A single-command Python CLI (336 LOC across four modules) that reads `terraform show -json` output
and renders a Markdown report through one Jinja2 template.

### 2.1 Capability inventory

| Capability | State | Where |
| :--- | :--- | :--- |
| Parse plan JSON → typed models | ✅ Pydantic, `resource_changes` only | `models.py` |
| Simplify actions to create/update/delete/replace | ✅ incl. `create`+`delete` → `replace` | `models.py:32` |
| Skip `no-op` / `read` | ✅ | `main.py:98` |
| Three-tier classification | ✅ `silent` / `normal` / `critical` | `config.py:26` |
| Per-action escalation (`critical_on`) | ✅ default `["delete","replace"]` | `config.py:28` |
| Detail suppression (`detail = "summary"`) | ✅ title-only rendering | `config.py:27` |
| Rule matching: exact type | ✅ `match_type` | `config.py:85` |
| Rule matching: regex on address | ✅ `match_pattern`, precedence over type | `config.py:82` |
| Attribute diff before/after | ⚠️ top-level keys only | `main.py:24` |
| `known after apply` | ⚠️ top-level `true` only | `main.py:40` |
| Tiered summary table | ✅ per action × tier, with `$\color{red}$` math hack | `report.md.j2:65` |
| Changes-by-resource-type table | ✅ plus separate 🔇 silent table | `report.md.j2:83` |
| Critical section hoisted above summary | ✅ the key UX decision | `report.md.j2:1` |
| Collapsible per-resource `<details>` | ✅ | `report.md.j2:12` |
| Output to file or stdout | ✅ `--output` | `main.py:175` |
| TOML config, CWD-discovered | ✅ `peek_config.toml` | `config.py:100` |

### 2.2 Deliberate non-goals (per `docs/architecture/01`)

Offline/local-only, no network, no state access, single command, one task. These are sound
constraints and worth keeping — they are also what makes the tool trivially safe to run in CI, which
is a selling point against SaaS competitors.

---

## 3. Strengths

**1. The tiering model is the differentiator, and it is well-reasoned.**
`docs/explanation/resource-tiers.md` articulates the "ignore / review / escalate" mapping and defends
three tiers over N. The `critical_on` mechanism (escalate a bucket on delete but not on create) is
the kind of nuance that only shows up after real operational pain. **No competitor surveyed in §5 has
an equivalent.** tfplan2md is explicit that it has *no* criticality classification.

**2. Silent disclosure is the right call.**
Counting silenced resources rather than dropping them ("47 `null_resource` changed") preserves trust
in the report. It is a small design detail that signals the author has actually been burned by
over-aggressive filtering.

**3. Hoisting the 🚨 section above the summary.**
Structurally correct for the failure mode that matters — a destructive op buried in a 400-line
report. It cannot be missed even on a skim.

**4. Documentation quality is far above the norm for a v1.0 side project.**
Full Diataxis split (tutorial / how-to ×4 / reference ×2 / explanation), plus an architecture set,
plus five OpenSpec capability specs. A published mkdocs-material site. This is a real asset for OSS
credibility — most competitors ship a README and nothing else.

**5. Engineering hygiene is strong.**
`uv`, ruff, pylint, pyright, `ty`, pre-commit, tox, renovate, release-please, conventional commits
with enforced scopes, codecov, PR title linting. 35 tests pass in 0.4s. Adding features here is
cheap and safe.

**6. The release pipeline is genuinely well built — better than most projects at this stage.**
`code-checks.yaml`'s `deploy-release` job publishes to PyPI via
[trusted publishing](https://docs.pypi.org/trusted-publishers/) (`id-token: write`,
`pypa/gh-action-pypi-publish`, no long-lived API token). It is dual-target: the release-please PR
branch publishes to **TestPyPI**, and a `v*.*.*` tag publishes to **PyPI**, each gated behind a
named GitHub environment. Combined with release-please, the path from merged commit to published
release is fully automated. **P2 needs no release work at all** — shipping 2.0 is a matter of
merging the release PR.

**7. Small, clean, readable core.**
Clear separation (parse / classify / render). The Jinja2 template is data-driven and swappable —
which is exactly what makes the HTML renderer in P2 a small job rather than a rewrite.

---

## 4. Weaknesses

### 4.1 Verified defects

Each of the following was **reproduced** by running `tf-peek` against a plan fragment containing a
replaced `google_sql_database_instance` with a sensitive attribute, a nested block, a value
containing `|` and a newline, a nested `after_unknown`, `replace_paths`, and an `output_changes`
entry.

---

**D1 — 🔴 Sensitive values are leaked in plaintext.** *(release blocker)*

`models.Change` does not parse `before_sensitive` / `after_sensitive`. Terraform marked `password`
sensitive; the report rendered:

```text
| `password` | `hunter2` | `s3cr3t!` |
```

For the stated primary surface — a GitHub PR comment — this publishes secrets to anyone with repo
read access, into a durable, indexed, notification-emailed artifact. tfplan2md masks by default and
requires `--show-sensitive` to opt out. tf-peek must do the same before any Action ships.

---

**D2 — 🔴 Report output is not reproducible across runs.**

`calculate_diff` iterates `set(before) | set(after) | set(unknown)`. Under Python's default hash
randomisation, attribute row order changes every run. Measured: **5 runs → 5 distinct MD5 hashes** of
the same report from the same input.

Consequences: sticky PR comments churn on every CI run; "has anything changed since last plan?"
diffing is impossible; golden-file tests can't be written. Fix is one `sorted()` call, but the bug
invalidates the whole sticky-comment strategy until it lands.

---

**D3 — 🟠 Unescaped values break the Markdown table.**

A `desc` attribute containing `has | pipe\nand newline` emitted:

```text
| `desc` | `has | pipe
and newline` | `x` |
```

The pipe adds a phantom column and the newline terminates the row — the table renders corrupted from
that row onward. This is not exotic: IAM policy JSON, `user_data`, descriptions, and shell
provisioners all routinely contain both characters.

---

**D4 — 🟠 Nested structures are dumped as Python `repr`, with no path-level diff.**

```text
| `settings` | `{'tier': 'db-f1-micro', 'flags': [{'n': 'a'}]}` | `{'tier': 'db-n1-standard-1', ...}` |
```

Two problems. First, it is Python `repr` (single quotes, `True`/`None`) in a report about JSON —
sloppy, and not copy-pasteable. Second, and worse: the reviewer must diff two blobs by eye to
discover that only `settings.tier` changed. On a real `google_container_cluster` or
`aws_ecs_task_definition` this cell is hundreds of characters wide and conveys nothing.

Semantic nested diffing is exactly where tfplan2md invests heavily (per-resource-type renderers for
firewall rules, NSG rules, etc.). This is the largest *rendering* quality gap.

---

**D5 — 🟠 Nested `after_unknown` is missed.**

`if k in unknown and unknown[k] is True` only matches top-level scalar unknowns.
`after_unknown: {"settings": {"ip_address": true}}` is a dict, so the check fails and the nested
unknown is silently dropped — or worse, surfaces as a spurious diff. Terraform nests unknowns
constantly.

---

**D6 — 🟠 Every documented invocation is wrong.**

README, tutorial, all four how-tos, and `docs/reference/cli.md` all say:

```bash
tf-peek generate plan.json
```

Typer collapses a single-command app, so the real usage is `tf-peek [OPTIONS] {json_path}`. The
documented form exits non-zero with `Got unexpected extra argument(s) (plan.json)`. **The very first
command in the tutorial fails.** For a tool courting external users this is the single highest-cost
bug per line-of-fix in the repo.

---

### 4.2 Missing capabilities

**M1 — Plan data left on the floor.** Only `resource_changes` is parsed. Ignored:

- **`replace_paths`** — *the* answer to "why is this being replaced?", the question a reviewer facing
  a 🚨 replace most urgently needs answered. tf-peek has a Critical Changes section that
  conspicuously fails to explain its own criticality. Highest-value gap in the list.
- `output_changes` — output diffs are frequently the human-meaningful part of a plan.
- `resource_drift` — out-of-band changes; increasingly a first-class review concern.
- `change.importing` / `moved` blocks (TF 1.5+) — imports will misrender.
- `terraform_version` / `format_version` — no compatibility gate, no provenance line in the report.
- `module_address` — parsed into the model but **never used**. No module grouping, despite modules
  being the natural review unit in real stacks. Competitors group by module.

**M2 — No CI gating.** Exit code is always 0. There is no `--fail-on-critical` / `--exit-code`. The
tool can *identify* a production database deletion and then cheerfully return success. Given the
tiering engine already computes exactly the signal a gate needs, this is a small change with
outsized value — and it converts tf-peek from a *reporter* into a *guardrail*, which is a
categorically stronger position (§6).

**M3 — Markdown is the only output.** No HTML (stated goal), no JSON, no SARIF, no plain text. The
Jinja2 indirection makes multi-format cheap; it just hasn't been exercised. Note also that
`--output` writes only Markdown while `docs/reference/cli.md` documents exit code 1 for
"configuration error" — unverified.

**M4 — stdout is broken for piping.** `main.py:181` uses `rich.print`, which interprets `[...]` as
markup. A Terraform address like `module.db["prod"]` contains `["prod"]` and will be mangled or
swallowed. `rich` also wraps to terminal width. Use `typer.echo` / plain `print` for machine-bound
output; reserve `rich` for an explicit `--pretty` terminal mode.

**M5 — No stdin.** Competitors support `terraform show -json | tool`. tf-peek requires a file path,
forcing a temp file in every pipeline.

**M6 — No shipped presets.** This is the strategic one. The entire value proposition is the tier
config, yet a new user starts with an **empty** config and therefore gets output strictly worse than
tf-summarize's. `config.toml` sits at the repo root as an example but is not installed, not
loadable by name, and not referenced by `load_config`. **The differentiator is currently opt-in,
undiscoverable, and requires the user to already know which resource types are dangerous.**

**M7 — Config discovery is CWD-only.** No upward walk to repo root, no `TF_PEEK_CONFIG` env var, no
`[tool.tf-peek]` in `pyproject.toml`, no global fallback. Running from a subdirectory silently
yields an empty config and a degraded report — a silent-failure mode that will be reported as "the
tiers don't work".

**M8 — No `--version`.** Table stakes; also makes bug reports harder.

### 4.3 Project-level gaps

- **`make integration-tests` is a stub.** `code-checks.yaml:159` runs a "Run Integration tests" step
  that resolves to `python-base-app.mk:41` → `echo "No op for now"`. CI reports a passing integration
  stage that verifies nothing. There are **no end-to-end or golden-file tests** — only 35 unit tests.
  This is why D1–D5 all survived to v1.0: every one of them is invisible to unit tests of
  `calculate_diff` and `resolve_tier` in isolation, and every one would have been caught by a single
  golden-file test rendering a realistic plan. Related: `project.mk:19`'s `poe-integration-tests`
  target invokes `poe pytest:integration`, which does not exist in `poe_tasks.toml`.
- **`pyproject.toml` description is `"Add your description here"`** — and this is what renders on the
  PyPI project page. Instant credibility loss for the "serious OSS contender" goal.
- **`AGENTS.md` says the repository is `yamkix`** (lines 3, 7) — copy-paste from a sibling project.
- **`docs/architecture/01` describes a config model that no longer exists** — it documents
  `config.ignore` and `config.summarize` (§"Filter resources"), superseded by the tier system.
- **No `CODE_OF_CONDUCT.md`, no issue templates beyond a single generic `ISSUE_TEMPLATE.md`,
  no `SECURITY.md`** — all expected of a project inviting contribution.
- **Repo-root clutter committed or present**: `.coverage`, `coverage.xml`, `generated/junit.xml`.
- **`docs/studies/` will auto-appear in the published mkdocs nav** (no explicit `nav:` in
  `mkdocs.yml`). Decide whether internal studies belong on the public site.

---

## 5. Market analysis

### 5.1 Landscape map

The space stratifies into four layers. tf-peek competes in layer 2 and should aim to annex layer 3.

| Layer | What it does | Examples |
| :--- | :--- | :--- |
| **1. Summarisers** | Count and list changes | tf-summarize, `terraform show` |
| **2. Renderers** | Human-readable plan → MD/HTML for review | **tf-peek**, tfplan2md, terraform-j2md, terraform-change-pr-commenter, Terraform Visual |
| **3. Risk / policy gates** | Judge the plan, block on violation | OPA/Conftest, Sentinel, Checkov, ControlMonkey |
| **4. Platforms** | Own the whole apply lifecycle | Spacelift, env0, Scalr, Atlantis, Digger, Terraform Cloud |

### 5.2 Direct competitors

| Tool | Lang | Stars | Output | Risk tiering | Sensitive masking | Nested diff | Notes |
| :--- | :--- | ---: | :--- | :---: | :---: | :---: | :--- |
| **tf-summarize** | Go | ~726 | table/tree/JSON/HTML/MD | ❌ | n/a | n/a | Category leader by adoption. Summary only, no diffs. Homebrew/asdf, GH Action. |
| **tfplan2md** | C#/.NET | ~171 | MD (GH/ADO/Bitbucket) | ❌ | ✅ default | ✅ semantic | The serious engineering competitor. SARIF ingest (Checkov/Trivy/TFLint/Semgrep), 92 Azure resource renderers, principal mapping, Homebrew, 14MB AOT Docker. Azure-first. |
| **terraform-j2md** | Go | ~68 | MD | ❌ | ❌ | ❌ | Minimal, stdin→stdout, fixed format. Closest in spirit to tf-peek v1. |
| **terraform-change-pr-commenter** | JS | ~50 | GH PR comment | ❌ | ❌ | ❌ | Pure delivery mechanism. Sticky comments, hide-previous, multi-file. |
| **Terraform Visual** | JS | — | interactive HTML | ❌ | ❌ | partial | The HTML incumbent. Upload-or-static-report UX. |
| **tf-peek** | Python | — | MD | ✅ **unique** | ❌ | ❌ | Best classification model, weakest rendering. |

### 5.3 Reading of the market

**The gap is real and it is exactly where tf-peek sits.** Every layer-2 tool renders *what* changes.
None of them lets you declare, per repository, *what you consider dangerous*. Layer-3 tools (OPA,
Sentinel, Checkov) do encode risk, but at a cost tf-peek does not impose: Rego or a policy DSL, a
separate mental model, and a binary pass/fail rather than a graduated review aid. **tf-peek's
`peek_config.toml` is the low-ceremony middle ground between "pretty renderer" and "policy engine",
and nobody is standing there.**

Three market forces support this position:

1. **Alert fatigue is the acknowledged pain.** The vendor content in this space (ControlMonkey,
   Spacelift) markets explicitly on "classifying safe vs. risky items to reduce noise". That is
   tf-peek's thesis, currently sold only as an enterprise SaaS feature. There is no OSS equivalent.
2. **Plan JSON as the automation contract is settled practice.** "Humans read the text plan; policy
   engines and automation use the plan JSON." tf-peek is correctly positioned on the JSON side.
3. **AI-assisted competition raises the floor on polish.** tfplan2md is openly "100% Copilot-built"
   and ships 2,729 commits, 84% coverage, OpenSSF badges, and Homebrew. Competing on *volume* of
   rendering features is a losing race. Competing on *the classification model* is not.

**The threats are equally clear.** Any layer-2 competitor could add a tiering config in a weekend —
it is not technically hard, it is a product insight. tf-peek's defensibility comes from getting
there first *with curated presets and a gating story*, not from the config schema itself. Speed on
P1 matters more than polish on P0. And Python is a distribution handicap against Go/AOT single
binaries: `uvx tf-peek` mitigates it, but a Homebrew formula and a Docker image are needed to
compete on installation friction.

---

## 6. Recommended positioning

> **tf-peek is the Terraform plan reviewer that knows what your team considers dangerous.**
> Declare your risk model once in `peek_config.toml`; get a review report that escalates what
> matters, silences what doesn't, and fails the build when something irreversible is on the table.

Two deliberate consequences of this framing:

**Annex layer 3.** Adding `--fail-on-critical` reclassifies the tool from "nicer plan renderer"
(a crowded, low-differentiation category) to "risk gate with an excellent report attached" (an empty
one). The tiering engine already computes the signal; the exit code is a few lines. This is the
highest leverage change in the entire document.

**Presets are the product, not the config schema.** A `tf-peek init --provider gcp` that writes a
curated, commented starter config is what makes the differentiator visible in the first 60 seconds.
Ship presets as versioned, community-contributable bundles (`presets/gcp.toml`, `aws.toml`,
`azure.toml`, `kubernetes.toml`) — this is also the natural contribution on-ramp for an OSS project,
requiring domain knowledge rather than Python knowledge.

Positioning explicitly **not** to pursue: competing with tfplan2md on per-resource-type semantic
renderers (they have a 92-type head start and an AI pipeline), or with the layer-4 platforms on
anything.

---

## 7. Recommendations

Ordered by leverage. P0 gates everything else.

### P0 — Correctness & safety (≈2–3 days)

Nothing ships until these land. D1 and D2 in particular invalidate the PR-comment strategy.

| # | Action | Addresses | Status |
| :--- | :--- | :--- | :--- |
| 0.0 | **Make `integration-tests` real.** Commit a fixture plan exercising sensitive values, nested blocks, pipes/newlines, nested unknowns, `replace_paths`, modules and outputs; assert against a golden `.md`. CI already calls the target — it just runs `echo "No op for now"`. Do this **first**: it is the harness that proves 0.1–0.5, and its absence is why all five defects reached v1.0 | §4.3 | ✅ Done — `archive/2026-08-16-integration-test-harness` |
| 0.1 | Parse `before_sensitive` / `after_sensitive`; mask as `(sensitive value)`; add `--show-sensitive` opt-out | **D1** | ✅ Done — `changes/mask-sensitive-values` |
| 0.2 | Sort the diff-key union before iteration (the only hash-order-dependent traversal in the report path); assert byte-identical output across repeated runs under differing `PYTHONHASHSEED` values | **D2** | ✅ Done — `changes/deterministic-report-output` |
| 0.3 | Escape `\|` and collapse newlines in table cells; truncate long values with a configurable `--max-value-width` | **D3** | ⬜ Not started |
| 0.4 | Render values as JSON, not Python `repr` | **D4a** | ⬜ Not started |
| 0.5 | Recurse `after_unknown` for nested dict/list unknowns | **D5** | ⬜ Not started |
| 0.6 | Decide the CLI shape — either `app.add_typer`/second command to keep `generate`, or drop `generate` from all docs. **Fix the tutorial first.** | **D6** | ⬜ Not started |
| 0.7 | Replace `rich.print` with `typer.echo` for report output; gate `rich` behind `--pretty` | **M4** | ⬜ Not started |
| 0.8 | Add `--version` | **M8** | ⬜ Not started |
| 0.9 | Fix `pyproject.toml` description (visible on PyPI); fix `AGENTS.md` `yamkix` references; correct `docs/architecture/01` config model | §4.3 | ⬜ Not started |

### P1 — Lean into the differentiator (≈4–5 days)

This is the moat. Prioritise 1.1 and 1.2 — they are what make tf-peek *not* a plan renderer.

| # | Action | Addresses |
| :--- | :--- | :--- |
| 1.1 | **`--fail-on-critical` / `--exit-code`** — non-zero when a `critical_on` action is present. Turns the tool into a CI gate. | **M2** |
| 1.2 | **Ship presets + `tf-peek init --provider gcp`** — curated `presets/{gcp,aws,azure,kubernetes}.toml`, packaged and loadable by name. Makes the differentiator visible immediately and creates the contribution on-ramp. | **M6** |
| 1.3 | **Surface `replace_paths`** — "Replaced because `settings[0].tier` changed" in the 🚨 section. Answers the reviewer's actual question. | **M1** |
| 1.4 | Config discovery: walk up to repo root, support `TF_PEEK_CONFIG`, support `[tool.tf-peek]` in `pyproject.toml` | **M7** |
| 1.5 | Nested path-level diffing — flatten to `settings.tier` rows rather than blob-vs-blob | **D4b** |
| 1.6 | Group by module using the already-parsed `module_address` | **M1** |
| 1.7 | `output_changes` section | **M1** |
| 1.8 | Precompile regexes once at config load | perf |

### P2 — Reach (≈4–5 days)

| # | Action | Addresses |
| :--- | :--- | :--- |
| 2.1 | **GitHub Action** — sticky comment, hide-previous, quiet-on-no-changes. Biggest single adoption lever; the Action is how people discover layer-2 tools. | goal |
| 2.2 | **HTML renderer** — second Jinja2 template, self-contained single file (inline CSS/JS), collapsible tiers, dark/light. Only Terraform Visual occupies this niche and it is not risk-aware. | goal |
| 2.3 | **stdin support** — `terraform show -json \| tf-peek -` | **M5** |
| 2.4 | **JSON output** — makes tf-peek composable for other tooling | **M3** |
| 2.5 | Docker image + Homebrew formula — offsets the Python distribution handicap vs Go competitors. The PyPI half of distribution is already solved (§3.6) | §5.3 |
| 2.6 | `resource_drift` and `change.importing` support | **M1** |
| 2.7 | `SECURITY.md`, `CODE_OF_CONDUCT.md`, structured issue templates | §4.3 |
| 2.8 | README rewrite led by a before/after screenshot of a report — the "🚨 above the fold" idea has to be *seen* | adoption |

### Deliberately out of scope

- Per-resource-type semantic renderers (tfplan2md has a 92-type lead)
- Cost estimation (Infracost owns it)
- Graph/dependency visualisation (Rover, Blast Radius)
- Anything requiring state access or network calls — the offline guarantee is a feature
- Competing with layer-4 platforms

---

## 8. Open questions

1. **CLI compatibility (D6)** — is `tf-peek generate` worth preserving? Nobody can be using it, since
   it has never worked. Recommendation: drop it, fix the docs, note it in the changelog.
2. **`--fail-on-critical` default** — opt-in flag, or on-by-default with `--no-fail`? Recommendation:
   opt-in for 2.0, revisit once presets are mature.
3. **Preset distribution** — packaged inside the wheel, or fetched from a separate repo? Packaged is
   simpler and preserves the offline guarantee; a separate repo scales contribution better.
   Recommendation: packaged, revisit if contribution volume justifies otherwise.
4. **Should `docs/studies/` be public?** No `nav:` in `mkdocs.yml` means it auto-publishes to the
   site today.
5. **Does GCP-first mean the default preset is GCP**, or that no preset loads unless named? The
   latter is more predictable; the former demos better.
6. **Version 2.0 or 1.x?** P0 changes stdout behaviour and possibly the command name — both breaking.
   Recommendation: 2.0.

---

## 9. Evidence appendix

Reproduction input (abridged) and observed output for §4.1.

**Input** — `google_sql_database_instance` being replaced, with a sensitive attribute, a nested
block, a pipe+newline value, a nested unknown, `replace_paths`, and `output_changes`:

```json
{
  "resource_changes": [{
    "address": "module.db[\"prod\"].google_sql_database_instance.main",
    "module_address": "module.db[\"prod\"]",
    "type": "google_sql_database_instance", "name": "main",
    "change": {
      "actions": ["delete", "create"],
      "before": {"password": "hunter2", "settings": {"tier": "db-f1-micro"},
                 "desc": "has | pipe\nand newline"},
      "after":  {"password": "s3cr3t!", "settings": {"tier": "db-n1-standard-1"}, "desc": "x"},
      "after_unknown": {"id": true, "settings": {"ip_address": true}},
      "before_sensitive": {"password": true},
      "after_sensitive": {"password": true},
      "replace_paths": [["settings", 0, "tier"]]
    }
  }],
  "output_changes": {"db_ip": {"actions": ["update"], "before": "1.2.3.4", "after": null}}
}
```

**Observed output** (detail section):

```text
| Property | Before | After |
| :--- | :--- | :--- |
| `password` | `hunter2` | `s3cr3t!` |                          ← D1 secret leaked
| `desc` | `has | pipe
and newline` | `x` |                                          ← D3 table broken
| `name` | `old` | `new` |
| `settings` | `{'tier': 'db-f1-micro', ...}` | `{'tier': ...}` | ← D4 repr blob, no path diff
| `id` | `null` | `(known after apply) ⏳` |
```

`settings.ip_address` (nested unknown) absent → **D5**. `replace_paths` absent → **M1**.
`output_changes` absent → **M1**. Module grouping absent → **M1**.

**Determinism check** — same input, five runs, `PYTHONHASHSEED=random`:

```console
$ for i in 1 2 3 4 5; do tf-peek plan.json -o r$i.md; md5sum r$i.md; done
0bdbff7d3a00001d88ea62c0ae64a1a5  r1.md
af71a9e12bf902c4e8e458bc7ab56c74  r2.md
98a516f146483ae5d61c7f7e8b6d593f  r3.md
db0b0506bd40663d5d89b70d6097fb61  r4.md
97ecd8a52d3da7fd2a6a7e56c70f83b0  r5.md
```

5 runs, 5 distinct outputs → **D2**.

**Documented invocation** — from `README.md`, `docs/tutorial/first-report.md`, and
`docs/reference/cli.md`:

```console
$ tf-peek generate plan.json
Usage: tf-peek [OPTIONS] {json_path}
Error: Got unexpected extra argument(s) (plan.json)
```

→ **D6**.

---

## Sources

- [tfplan2md](https://github.com/oocx/tfplan2md) · [docs site](https://oocx.github.io/tfplan2md/)
- [tf-summarize](https://github.com/dineshba/tf-summarize)
- [terraform-j2md](https://github.com/reproio/terraform-j2md)
- [terraform-change-pr-commenter](https://github.com/liatrio/terraform-change-pr-commenter)
- [terraform-plan-comment](https://github.com/borchero/terraform-plan-comment)
- [Terraform Visual](https://github.com/hieven/terraform-visual)
- [Top 5 Terraform Visualization Tools for 2026 — Spacelift](https://spacelift.io/blog/terraform-visualization)
- [Terraform Guardrails: Enforce Safe IaC Changes — Spacelift](https://spacelift.io/blog/terraform-guardrails)
- [Terraform Plan Made Simple — ControlMonkey](https://controlmonkey.io/resource/terraform-plan-made-simple/)
- [Top Terraform Tools to Know in 2026 — env0](https://www.env0.com/blog/top-terraform-tools-to-know)
- [Tools to Visualise your Terraform Plan — Overmind](https://overmind.tech/resources/terraform-tools/plan-comparisons)
