# Adversarial Review — `2026-08-20-surface-plan-causation`

Adversarial review of the branch `feat/surface-plan-causation` against the artifacts in this change
directory. Three independent reviewers (Skeptic, Architect, Minimalist) plus a lead judgment.

- **Reviewed at**: commit `2093332` (`feat(report): surface plan causation via replace_paths and action_reason`)
- **Scope**: Large — 25 files, +1724/-12
- **Initial verdict**: **REJECT** — two accepted high-severity findings
- **Current status**: all 15 accepted findings remediated; see [Remediation](#remediation) and
  [Verification](#verification)

## Intent under review

The 🚨 Critical Changes section asserts danger without explaining it. This change surfaces
Terraform's own stated causation — `replace_paths`, `action_reason`, and the `change.actions`
ordering that distinguishes destroy-then-create from `create_before_destroy` — as neutral prose in
resource detail blocks and on the collapsed `<summary>` line, without inferring intent or severity
and without touching tiering, `critical_on`, `--fail-on-critical` or exit codes.

Source: the artifacts in this directory (`proposal.md`, `design.md`,
`specs/plan-causation-rendering/spec.md`, `tasks.md`) — an authoritative spec, not a reconstruction.

## Findings

Severity is the lead judgment's, not necessarily the raising reviewer's. `Lens` credits every
reviewer who raised the finding independently.

|#|Severity|Finding|Lens|Judgment|Status|
|---|---|---|---|---|---|
|[F1](#f1)|high|Forcing path descends into a wholly-sensitive attribute and prints its map key|Skeptic|accept|fixed|
|[F2](#f2)|high|Body reason emitted unwrapped; `escape_for_markdown` does not neutralize `<`/`&`|Skeptic, Architect, Minimalist|accept|fixed|
|[F3](#f3)|medium|Forcing-path rendering not gated on the replace action|Skeptic, Architect|accept|fixed|
|[F4](#f4)|medium|`detail = "summary"` contract changed with no spec delta; reference doc now false|Architect|accept|fixed|
|[F5](#f5)|medium|Three of four structural assertions in the hostile-path regression cannot fail|Skeptic|accept|fixed|
|[F6](#f6)|medium|Strict `replace_paths` typing aborts the whole report; rejects explicit `null`|Skeptic|accept|fixed|
|[F7](#f7)|medium|`destroy_before_create` raises `ValueError` instead of being total|Skeptic, Architect|accept|fixed|
|[F8](#f8)|medium|Escaping committed at dataclass construction; report shape split across two layers|Architect|accept|fixed|
|[F9](#f9)|low|Empty forcing path emits an empty `<code>` and an unmatched backtick pair|Skeptic, Architect|accept|fixed|
|[F10](#f10)|low|Pipe escape mutates prose content for no safety benefit|Architect|accept|fixed|
|[F11](#f11)|low|`_KNOWN_REASONS["replace_because_cannot_update"]` is unreachable|Minimalist|accept|fixed|
|[F12](#f12)|low|Empty-string `action_reason` produces a nonsense sentence|Skeptic|accept|fixed|
|[F13](#f13)|low|Hand-rolled HTML escaping duplicates `html.escape`; newline collapse untested|Minimalist|accept|fixed|
|[F14](#f14)|low|Summary line bounded by path count, not rendered length|Architect|accept|fixed|
|[F15](#f15)|low|Test-surface duplication: tests that cannot fail independently|Minimalist|accept|fixed|
|[R1](#r1)|—|Drop the constant `**Mechanism:**` line for default destroy-then-create|Minimalist|reject|no action|
|[R2](#r2)|—|Make the five `causation.py` helpers private|Minimalist|reject|no action|
|[R3](#r3)|—|Add pipe/backtick escaping to the `<summary>` HTML context|Skeptic|uncertain|superseded|
|[R4](#r4)|—|Return a total `Causation` instead of `Causation \| None`|Minimalist|reject|no action|
|[R5](#r5)|—|OpenSpec artifact volume; body/summary path duplication|Minimalist|reject|no action|

## Remediation

### F1 — Forcing paths bypassed sensitive-value masking {#f1}

**Defect.** `resolve_causation()` received only `replace_paths` and `action_reason`, never the
sensitivity markers. A plan with `after_sensitive: {"data": true}` and
`replace_paths: [["data", "STRIPE_LIVE_KEY"]]` rendered `forces replacement:
<code>data.STRIPE_LIVE_KEY</code>` on the always-visible summary line and
`**Forces replacement:** \`data.STRIPE_LIVE_KEY\`` in the body, while the table row read
`| \`data\` | \`(sensitive value)\` | \`(sensitive value)\` |`. `design.md` justified this on the
premise that markers "mark leaf *values*, never map keys" — false for an attribute-level `true`,
which covers the whole value including its keys. `diff.py` fails **closed** on the identical marker
(masking the entire top-level attribute when any leaf is truthy); causation failed **open** on it,
so the report held two contradictory sensitivity policies. Terraform's own output prints
`data = (sensitive value) # forces replacement` and never the sub-key.

**Fix.** `_is_sensitive` is now public `is_sensitive` in `diff.py`, and `causation.py` truncates a
path at the first step whose marker subtree contains any truthy leaf — the same granularity at which
`calculate_diff` masks the attribute, so the path never names anything the table does not.
`resolve_causation` takes the `(before_sensitive, after_sensitive)` pair, and `report.py` passes
`None` under `--show-sensitive` exactly as it already does for the diff. One policy, one
implementation, fail-closed on both surfaces.

### F2 — Body reason could inject raw HTML and corrupt the block {#f2}

**Defect.** `escape_for_markdown` neutralized only `|`, backtick and CR/LF. `body_paths` survived
only because the template wrapped it in backticks; `body_reason` was emitted unwrapped into a
Markdown paragraph nested inside a raw-HTML `<details>` block, where `<` and `&` are live. An
`action_reason` of `delete_because_</details><img src=x onerror=alert(1)>` emitted a raw
`</details>` that closes the enclosing collapsible, pushing the attribute table out of the block —
"corrupt report structure or inject markup", which the capability's escaping requirement forbids
"in every context where the report presents them". A fresh instance of ledger defect D3 in a
location `tests/integration/test_defects.py` does not reach. The `<summary>` copy of the same string
was correctly escaped, so the two contexts disagreed on identical input.

**Fix.** Escaping moved out of dataclass construction into three context-named functions registered
as Jinja filters (see [F8](#f8)), so the context that applies an escape is the context that knows
it:

|Filter|Context|Neutralizes|
|---|---|---|
|`in_code_span`|Markdown text inside a backtick span|backtick → `\u0060`, CR/LF → `\n`|
|`in_markdown`|Markdown paragraph prose|`&`, `<`, backtick → HTML entities, CR/LF → `\n`|
|`in_html`|`<summary>` raw-HTML element content|`html.escape`, CR/LF → `\n`|

`in_markdown` uses entities (`&amp;`, `&lt;`, `&#96;`) rather than literal escape text: an entity is
inert as a Markdown delimiter yet displays as the original character, so the reason stays faithful
to what Terraform reported. Inside a code span entities are *not* decoded, which is why
`in_code_span` must substitute the backtick instead — the one deliberately lossy substitution left,
documented as such. New fixture `causation-hostile-reason.json` carries `</details>`, an
`<img onerror=…>`, an ampersand, a backtick and a raw line feed in `action_reason`, asserted
structurally.

### F3 — Forcing paths rendered for non-replace actions {#f3}

**Defect.** `mechanism` was gated by `action == "replace"` but `resolve_causation` on the line above
was not, and the template labelled the result `**Forces replacement:**` unconditionally. An
`actions: ["update"]` change carrying `replace_paths` rendered `**Forces replacement:** \`ami\``
under the Update heading — the report asserting a replacement that is not happening, contradicting
its own action classification and the spec scenario "Non-replace changes state no forcing paths",
which is written as a property of the report but was implemented as an assumption about the input.

**Fix.** `resolve_causation` takes the `replacement_mechanism` tri-state ([F7](#f7)) and renders
forcing paths only when it is not `None`. The reason stays unconditional — deletions legitimately
carry `delete_because_*`. New fixture `causation-non-replace-paths.json` pins it.

### F4 — `detail = "summary"` contract changed without a delta {#f4}

**Defect.** `proposal.md` asserted "Modified Capabilities: None" and promised "**No changes** to …
`docs/reference/configuration.md`", but `configuration.md` stated "Only the resource address is
shown; the attribute diff is omitted" — false after this change, and contradicting the
`resource-tiers.md` sentence the branch added. The in-report notice was self-contradicting too: the
causation callout rendered *above* `> ℹ️ *Details hidden by configuration…*`, so a summarized block
showed two lines of detail followed by a claim that details were hidden.

**Fix.** Added `specs/resource-tier-config/spec.md` with a MODIFIED delta narrowing the `detail`
requirement to attribute *values*, corrected the "Modified Capabilities" and "Impact" sections of
`proposal.md`, fixed the `configuration.md` table row, and reworded the notice to
`> ℹ️ *Attribute values hidden by configuration (filtered resource).*`.

### F5 — Vacuous assertions in the hostile-path regression {#f5}

**Defect.** `design.md` calls this fixture "the single highest-consequence item in the change", yet
three of its four structural assertions could not fail: the column-count assertion ran over the
attribute table, which causation never reaches; `summary_line.count("\n") == 0` ran on a string
produced by `splitlines()`; and `"<" not in summary_html or "<code>" in summary_html` has an
unconditionally true right disjunct whenever paths exist. The spec's "consistent number of cell
delimiters" and "no code span opened by the report is closed by the key's content" were unpinned.

**Fix.** Assertions now run against the causation output itself: zero cell delimiters on the
forcing-path line, an even backtick count on it, balanced `<summary>`/`</summary>` counts across the
report, no line break between them, and no raw `<`/`>` in the summary fragment. The two tautologies
are deleted rather than left as false assurance.

### F6 — Strict `replace_paths` typing aborted the whole report {#f6}

**Defect.** `list[list[str | int]]` rejected the entire plan on one unexpected step:
`[["settings", 1.5]]` produced `plan does not match the expected structure`, exit 1, no report.
`"replace_paths": null` failed too, while `before`, `after`, `after_unknown`, `before_sensitive` and
`after_sensitive` all accept an explicit null — and on `main` every one of those plans rendered.
That is the exact inversion of this change's own reasoning for keeping `action_reason` an open
`str`: a lost display hint must not become a total parse failure.

**Fix.** The field is `list[list[Any]]` with a `mode="before"` validator mapping `None` → `[]`, and
`_render_step` falls back to a JSON-encoded subscript for any step that is neither `str` nor `int`.
Booleans are matched before `int` (they are an `int` subclass) so a JSON `true` renders as `[true]`
rather than silently becoming index `[1]`.

### F7 — `destroy_before_create` raised instead of being total {#f7}

**Defect.** `list.index` raises when the element is absent, so the property threw `ValueError` for
every create-only, update-only or delete-only change. Latent — the single caller was guarded — but a
public model property whose docstring said "Only meaningful when `is_replacement` is True", which
reads as "returns a meaningless value", not "raises"; and the model held two notions of replace with
asymmetric safety.

**Fix.** Replaced by `replacement_mechanism: Literal["destroy_first", "create_first"] | None`, total
by construction: `None` means "not a replacement". `report.py`'s `action == "replace"` guard is gone
— the tri-state carries that fact — and the same value drives the [F3](#f3) path gate.

### F8 — Escaping committed at construction; report shape split in two {#f8}

**Defect.** `Causation` stored only terminal presentation (`body_paths`/`body_reason`
Markdown-escaped, `summary_html` HTML-escaped *and* `<code>`-wrapped *and* capped *and* joined),
while `resolve_causation` computed the neutral forms and discarded them. The *decision* (which
paths, which reason, redundancy suppression) was inseparable from two specific renderings, so the
JSON-output and `resource_drift` consumers this change's own design anticipates could neither
consume `Causation` (corrupted path strings, embedded tags) nor bypass it (the precedence rule lives
nowhere else). It was also the root cause of [F2](#f2). Separately, the label, code-wrapping and
joining decisions were each made twice in two dialects, against `AGENTS.md`'s "report shape lives in
the Jinja template".

**Fix.** `Causation` is neutral data: `paths`, `reason`, `mechanism`, `summary_paths`,
`summary_remainder`. All escaping and all markup moved to the template — a `causation_summary()`
macro owns the `<code>` wrapper, the joiner, the `; ` separator and the remainder note; the three
escapers are Jinja filters. `causation.py` keeps what its module docstring claims: path rendering,
reason phrasing, precedence, the cap decision, and the escape functions themselves.

### F9 — Empty forcing path emitted malformed markup {#f9}

**Defect.** `render_forcing_path([])` returned `""` and `resolve_causation` tested the list rather
than the rendered forms, so `replace_paths: [[], ["ami"]]` rendered
`**Forces replacement:** \`\`, \`ami\`` — a double-backtick sequence CommonMark scans as an
unmatched opener — plus an empty `<code></code>` that also consumed a summary cap slot.

**Fix.** `render_forcing_paths` filters falsy rendered forms, so an empty path collapses to "no
paths stated" and `resolve_causation` returns `None` when that is all there was.

### F10 — Pipe escape mutated prose content {#f10}

**Defect.** `|` → literal text `\u007c` was inherited from `format_report_value`, where it is
necessary because the value lands in a table cell. Neither causation fragment does. A reason
containing `| pipe` rendered as `\u007c pipe` — the report showing a string the plan did not say, in
a feature whose premise is faithful reporting.

**Fix.** No causation escaper substitutes `|`; both live in paragraph contexts where a pipe is
ordinary text. `format_report_value` is unchanged — there the escape is load-bearing.

### F11 — Unreachable `replace_because_cannot_update` phrasing {#f11}

**Defect.** Terraform 1.9.5 `getAction` sets that reason only inside `case !reqRep.Empty():`, and
emits the same non-empty path set as `RequiredReplace` → `replace_paths`. The code therefore always
arrives with paths, and the precedence rule always discards the phrase `_KNOWN_REASONS` had just
computed.

**Fix.** Deleted the table entry and its unit parametrize case. **Narrowed from the reviewer's
recommendation:** the `paths and` conjunction in the precedence rule is *kept*. Dropping it would
suppress a recognized reason unconditionally, which the spec does not state; keeping it means a
hypothetical pathless emission degrades to the documented passthrough sentence, which is precisely
the behaviour the reviewer accepted as the fallback.

### F12 — Empty-string `action_reason` {#f12}

**Defect.** The guard was `is not None`, so `""` produced `**Reason:** reason reported by Terraform:
""`. Reachable only from a third-party plan producer (Terraform omits the field).

**Fix.** The guard is now truthiness.

### F13 — Hand-rolled HTML escaping; untested newline collapse {#f13}

**Defect.** `escape_for_summary_html` was a verbatim reimplementation of `html.escape`. Separately, a
newline can never survive into a rendered *path* — a non-identifier step goes through `json.dumps`,
which already escapes it — so the integration assertion that appeared to cover the newline case
passed on `json.dumps`'s work and would still pass with the collapse deleted. Its one reachable
producer is a hostile reason, which no fixture exercised.

**Fix.** `in_html` delegates to `html.escape`. The newline collapse is kept and is now pinned by the
raw line feed in `causation-hostile-reason.json`, which reaches it through the reason path.

### F14 — Summary line bounded by count, not length {#f14}

**Defect.** Nothing capped step length: three long Kubernetes/GCP label keys push the resource
address off screen, defeating the stated purpose of putting causation on the summary line, while
`design.md` cited "the `<summary>` line is finite" as the cap's premise.

**Fix.** A rendered-character budget applies alongside the count cap, and a single path exceeding the
budget on its own is truncated with an ellipsis. Both are within the spec, which fixes "bounded,
with a remainder indicator" and no specific rule. The lexical sort order is unchanged — it is
spec-fixed and deterministic.

### F15 — Test-surface duplication {#f15}

**Defect.** `test_change_replace_paths_preserves_supplied_value` and
`test_resource_change_action_reason_preserves_unrecognized_value` asserted that a plain pydantic
field with no validator returns what was passed — testing pydantic.
`test_resolve_causation_returns_frozen_dataclass` asserted `isinstance`, which every other test in
the file depends on transitively. `causation-create-before-destroy.json` could not fail without the
kitchen-sink golden failing first (task 5.4 added the same `["create", "delete"]` + `replace_paths`
shape, and the golden pins both strings verbatim). Five of the six known-reason integration cases
restated the unit phrasing table without exercising a different code path.

**Fix.** All of those are deleted. Kept: the two default-value tests (they defend real decisions —
`default_factory` over `None`, open `str` over `Literal`), one known-reason integration case, and the
passthrough case. The `replace_paths` round-trip test is *replaced* rather than deleted, because the
field now has a validator ([F6](#f6)) and therefore real behaviour to defend.

## Rejected and superseded findings

### R1 — Drop the constant `**Mechanism:**` line {#r1}

Rejected. The alert-fatigue argument is the project's own thesis and was applied honestly, but
suppressing the default makes *absence* ambiguous: the reader cannot distinguish "destroy-first"
from "the tool did not say". `specs/plan-causation-rendering/spec.md` requires the report to state
which mechanism applies for both directions, and `design.md` already rejected the model-only variant
as a repeat of the unused-`module_address` anti-pattern. Rendering both uniformly is what makes the
`create_before_destroy` line legible.

### R2 — Make the five `causation.py` helpers private {#r2}

Rejected. `formatting.py:format_report_value` is public and unit-tested directly; convention rule 8
prefers private *helpers*, and these are the module's tested API, not internals. Style, not
substance. (The module's public surface did shrink incidentally: `mechanism_statement` became a
lookup table and the escapers are now registered as filters.)

### R3 — Add pipe/backtick escaping to the `<summary>` context {#r3}

Superseded by [F2](#f2)/[F13](#f13). The reviewer confirmed the characters are inert there, because
`<details>` opens a CommonMark type-6 HTML block. `in_html` now delegates to `html.escape`, which
does not touch either character; the residual renderer-dependency argument is noted and not acted
on, since acting on it would reintroduce lossy substitution in a context where it buys nothing.

### R4 — Return a total `Causation` instead of `Causation | None` {#r4}

Rejected. Trades one resolver branch for three template guards on empty state, and
`None`-means-no-explanation matches the spec's "a change with no stated cause receives no
explanation". `Causation` is now returned whenever there is *anything* to say, mechanism included,
so the null case is unambiguous.

### R5 — OpenSpec artifact volume; body/summary path duplication {#r5}

Rejected; the reviewer reached the same conclusion on both. The 637 lines of artifacts document
load-bearing rejected alternatives, and the body/summary duplication is the deliberate
skimmer/reader split `design.md` argued for.

## What went well

- **Determinism holds.** Re-ran task 7.3 independently: four `PYTHONHASHSEED` values over a plan
  with duplicate and unsorted forcing paths produced one MD5. Sorting the *rendered* form keeps sort
  key and displayed text identical, as designed.
- **The rejected alternatives are load-bearing.** Splitting `replace` into `replace`/`replace_cbd`
  would let adding `create_before_destroy` to a `lifecycle` block silently de-escalate a resource
  matched by `critical_on = ["delete", "replace"]`. The design caught that unprompted.
- **The open-`str` `action_reason`** — contrasted explicitly against the fail-closed sensitivity
  posture — is the right call for the right stated reason, and the path-notation grammar renders
  correctly for every step shape the format spec permits. No new configuration knobs were added.

## Verification

Run after remediation, on the working tree. Tasks 8.1–8.12 in `tasks.md` map each finding to its
change.

|Check|Result|
|---|---|
|`uv run poe style`|pass — 3 files reformatted, then clean|
|`uv run poe lint:all`|pass — `ruff format --check`, `ruff check`, `pylint` 10.00/10, `ty check`|
|`uv run poe test`|pass — **206 passed**, 2 snapshots (was 187 before remediation)|
|`uvx pre-commit run --all-files`|pass — all hooks, `markdownlint-cli2` included|
|Determinism|pass — 5 `PYTHONHASHSEED` values × 2 fixtures (duplicate/unsorted paths, hostile key) → one MD5 each|
|`openspec validate … --strict`|pass — "Change '2026-08-20-surface-plan-causation' is valid"|
|Golden review|only the reworded `detail = "summary"` notice moved (3 lines in the demo golden). The kitchen-sink golden is **byte-identical**, so moving all escaping and markup into the template changed no rendered output.|

### Finding reproductions

Each high/medium defect was reproduced before the fix and re-run after it.

|Finding|Before|After|
|---|---|---|
|F1|`forces replacement: <code>data.STRIPE_LIVE_KEY</code>` beside `\| data \| (sensitive value) \|`|`forces replacement: <code>data</code>` — the key never appears in the report|
|F2|raw `</details><img src=x onerror=alert(1)>` in the body; rendered HTML unbalanced, decoy collapsible opened|`&lt;/details>&lt;img …>`; rendered through CommonMark, `<details>`/`<summary>` counts balanced, no live tag, no injected heading|
|F3|`**Forces replacement:** \`ami\`` under the Update heading|no forcing path and no mechanism on the update; its stated reason still renders|
|F6|`[["settings", 1.5]]` and `"replace_paths": null` each aborted the report with exit 1|both render; the float step shows as `settings[1.5]`, a JSON `true` as `[true]`, an empty path is dropped|
|F5|3 of 4 structural assertions passed with the escaping removed|assertions now run on the causation line itself: 0 cell delimiters, even backtick count, exact `[4, 4, 4]` table columns, balanced HTML elements|
|F7|`ResourceChange(…, actions=['create']).destroy_before_create` → `ValueError`|`replacement_mechanism` returns `None`; pinned by a parametrized test over 5 non-replacement action lists|

### Residual risk

A path step is still rendered verbatim inside a code span, where a backtick must be substituted
(`\u0060`) because CommonMark does not decode entities there. That substitution is the only place the
report shows something other than what the plan said, and it is confined to a character no Terraform
attribute path contains in practice. Every other context now preserves the plan's text exactly.
