## Context

See `proposal.md — Why` for motivation. The constraints that shape the approach:

- `build_report_data()` (`src/tf_peek/report.py:76`) walks each non-`no-op`/`read` change once and
  builds a plain `dict` `resource_entry` (`report.py:113`) consumed by both detail macros in
  `src/tf_peek/templates/report.md.j2`. Causation has to arrive through that dict; there is no second
  pass.
- `calculate_diff()` iterates **top-level keys only** (`src/tf_peek/diff.py:228`). A replace path
  such as `settings[0].tier` has no corresponding table row to attach itself to — the table has a
  `settings` row.
- The Jinja2 environment runs `autoescape=False` (`report.py:151`). The `<summary>` line is fed
  `f"{rc.type}.{rc.name}"` (`report.py:115`), both HCL identifiers, so it is currently safe by
  accident rather than by construction.
- `PeekConfig` has exactly one field and `load_config()` reads exactly one key, discarding every
  other key in the file silently (`src/tf_peek/config.py:108`).
- `ResourceChange.is_replacement` (`src/tf_peek/models.py:31`) tests set membership, so it is
  order-insensitive by construction.
- `format_report_value()` (`src/tf_peek/formatting.py:16`) JSON-serializes its input. It is the wrong
  tool for a path: it would render `settings[0].tier` as a quoted JSON string literal.

## Goals / Non-Goals

**Goals:**

- Explain every 🚨 verdict the plan gives tf-peek the information to explain, and explain nothing
  else — no inferred, interpolated or invented reasons.
- Put the explanation where a reviewer who never expands a `<details>` block still sees it.
- Make the new string surfaces safe **by construction**, in both the Markdown-cell and HTML contexts,
  rather than relying on the accident that resource types and names are identifiers.
- Survive Terraform adding reason codes without a parse failure.
- Leave the tiering engine, the 🚨 bucketing rule, and the exit-code gate untouched.

**Non-Goals (design-level, beyond the proposal's scope statement):**

- A per-row "forces replacement" badge in the diff table. It needs path-level diff rows, i.e. study
  item P1 1.5; see the *Row badges deferred* decision.
- Splitting `replace` into two actions in `ACTION_ORDER` / the `Action` enum. See the *Replacement
  mechanism* decision for why this is not merely deferred but rejected.
- Any reason- or path-driven tier escalation. `always_critical_when_reason` is a genuinely good
  follow-up, but `2026-08-18-fail-on-critical-gate/design.md:29-31` rules out a second policy
  language and the gate is two days old; perturbing its semantics now costs the clean story for a
  nuance.
- Applying the causation renderer to `resource_drift` (study 2.6). `resource_drift` reuses the
  `resource_changes` object structure, so it will reuse this renderer for free when it lands.

## Decisions

**`action_reason` is an open `str`, not a `Literal` — this change fails open, and that is the
opposite of the sensitivity decision on purpose.** The format spec is explicit: reason codes "are
display hints only and the set of possible hints may change over time. Users of this must be prepared
to encounter unrecognized reasons and treat them as unspecified reasons." A pydantic `Literal` of the
nine documented codes would reject the whole plan on a code introduced by a future Terraform release —
turning a lost display hint into a total parse failure. Contrast `_is_sensitive()`
(`src/tf_peek/diff.py:67`), which deliberately fails **closed** on unexpected marker shapes. Both are
correct because the failure costs differ by orders of magnitude: mishandling a sensitivity marker
publishes a secret into a durable, notification-emailed PR comment (study §4.1 D1); mishandling a
reason code loses a sentence. The asymmetry is recorded here so it reads as a decision rather than an
inconsistency.

**Paths win over reason, and `replace_because_cannot_update` is suppressed when paths exist.** The
two fields are complementary rather than redundant, but they do overlap in exactly one case: a
provider-forced replace typically carries both `replace_paths` and
`action_reason = "replace_because_cannot_update"`. Rendering both produces "replaced because the
provider cannot update in place; forces replacement: `settings[0].tier`" — the second clause already
implies the first, and the study's entire thesis (§5.3) is that alert fatigue is the enemy.
`replace_because_tainted` and `replace_by_request` arrive *with* empty paths and are therefore the
only signal available. So: paths present → paths; paths absent → phrased reason; neither → render
nothing. Rejected alternative: always render both fields and let the reader deduplicate. Rejected
because the redundant pair is the *common* case, so the noise would be the default experience.

**HCL-style path rendering (`settings[0].tier`), accepting one unresolvable ambiguity.** Considered
`settings.0.tier` (unambiguous, jq-flavoured) and `settings → 0 → tier` (unambiguous, escaping-
friendly). Both rejected on familiarity: a reviewer may well be reading the human-readable
`terraform plan` output alongside the report, where the forcing attribute is annotated in HCL shape,
and a second dialect makes eyeball-matching harder for no gain. The grammar: numeric step → `[0]`;
identifier-safe string step → `.tier`; any other string step → a JSON-quoted subscript,
`["kubernetes.io/role"]`; no leading dot on the first step. The accepted cost: the format spec says
each step "will be a number or a string", and a *string* key on a map is indistinguishable in JSON
from a string attribute name, while a numeric map key would have been serialized as a string and
therefore renders as `["0"]` rather than `[0]`. That is a faithful rendering of what the plan
actually says, not a guess — tf-peek has no schema to consult and will not pretend to.

**A dedicated path/reason formatter, not `format_report_value()`.** The existing formatter
JSON-serializes, which is exactly right for values and exactly wrong for a path — it would emit
`"settings[0].tier"`, quotes included. The new formatter shares the *discipline* established by
`safe-value-rendering` (a rendered fragment can never gain a table column, break a row, or close its
own code span) without sharing the implementation. Rejected alternative: generalize
`format_report_value()` with a mode flag. Rejected because a two-mode formatter whose modes disagree
about JSON quoting is harder to reason about than two functions, and the escaping *sets* differ (see
next decision).

**Two escaping contexts, and the HTML one is new to this codebase.** The body callout lands in
Markdown; the short form lands inside `<summary>`, which is HTML. The union of hostile characters is
therefore larger than anything `safe-value-rendering` currently covers: `|` and backtick and
CR/LF for the table context, plus `<`, `&` and `"` for the HTML one. Map keys are the vector —
`kubernetes.io/role` is benign, but nothing prevents a key containing a pipe, a newline, or `<b>`.
Two consequences:

1. The short form uses an explicit `<code>` element rather than Markdown backticks. The template has
   already committed to HTML inside `<summary>` (`report.md.j2:40` uses `<b>`), and Markdown support
   inside `<summary>` is renderer-dependent, so relying on backticks there would make correctness
   depend on which Markdown engine renders the report.
2. A hostile-map-key fixture is a required part of this change, not a nice-to-have. Without it, this
   feature is a fresh instance of study defect D3 in a location the existing D3 regression tests do
   not reach.

**Short form in `<summary>`, full form in the body.** The justification for the 🚨 section's
existence is that it "cannot be missed even on a skim" (study §3.3). An explanation sealed inside a
collapsed `<details>` is invisible to exactly the reader the section was built for. Rejected
alternative: body-only (simpler, smaller template diff) — rejected because it optimizes for the
reader who was already going to expand the block, i.e. the one who needed help least. The `<summary>`
line is finite, so the displayed path list is bounded with a remainder indicator; the full list is
always in the body, so the cap is a display concern and never withholds information. Because paths
are sorted, *which* paths appear under the cap is deterministic.

**Row badges deferred to P1 1.5, not shipped coarse.** Terraform's own text output annotates the
forcing attribute line with `# forces replacement`, which is the obvious thing to mirror. It cannot
be mirrored faithfully yet: `calculate_diff` produces one row per top-level key, so a
`settings[0].tier` path can only mark the `settings` row — technically true, imprecise, and it
trains readers to distrust the marker. Once P1 1.5 flattens the diff to path-level rows, the badge
lands on the exact row and the same causation data drives it with no rework. Shipping the coarse
version first would have to be un-shipped.

**Replacement mechanism: body callout only (3C), and the action-vocabulary split is rejected
outright.** Considered five placements. Model-only (parse the ordering, render nothing) is rejected
because study §4.2 already indicts `module_address` as "parsed into the model but **never used**", and
repeating that pattern inside the change that fixes an adjacent instance of it is self-defeating.
A `<summary>` chip is rejected as real-estate contention: that line is already carrying the address,
the causation short form and potentially the 💥 badge, and a replace-ordering nuance only matters
*after* the reader has decided to read the resource. Splitting `replace` into `replace` /
`replace_cbd` is rejected for a stronger reason than cost: existing configs say
`critical_on = ["delete", "replace"]`, so a split either needs `"replace"` to alias both new actions
(a second matching mechanism beside `match_type`/`match_pattern`) or lets adding
`create_before_destroy` to a `lifecycle` block **silently de-escalate a critical resource**. The
second is unacceptable and the first is the kind of parallel convention this repository forbids;
the split would also grow `ACTION_ORDER`, the `Action` enum and its sync test, the summary table, and
`report.md.j2:88`'s column set, immediately after the gate shipped.

**The mechanism callout states mechanism, not consequence.** "Destroyed before its replacement is
created", not "expect downtime". Destroy-first means downtime for compute, **data destruction** for a
bucket or disk, and a **new secret value** for a `random_password`; and `create_before_destroy` is
not safe either — it can fail on name collisions, port conflicts or quota. tf-peek has no resource
schema and cannot know which applies, so asserting a consequence would be over-claiming. Study §3
spends five points earning the credibility that a wrong severity claim spends.

**Causation survives `detail = "summary"`.** The `is_summarized` branch (`report.py:92`) currently
short-circuits diff computation, and the template replaces the whole table with "Details hidden by
configuration". `summary` suppresses **values**; a replace path is an attribute *name* and a reason
code is plan metadata, so keeping them is the coherent reading of the setting and makes `summary` a
usable middle setting for a noisy-but-important resource type instead of a near-`silent`. Note this
behaviour was never specified — the current specs only fix `detail`'s default (`resource-tier-config`
requirement "detail field defaults to full"), so the new capability establishes it rather than
changing it.

**Sensitivity is unaffected, deliberately.** A replace path can point at an attribute masked as
`(sensitive value)`. The path is the attribute's *name*, not its value, and Terraform's own output
prints `# forces replacement` beside a redacted value, so rendering the path is neither a leak nor a
divergence from Terraform's behaviour. `before_sensitive`/`after_sensitive` mark leaf *values*, never
map keys, so the plan carries no signal that a key itself is sensitive and tf-peek will not invent
one. `sensitive-value-masking` needs no change.

**Sorted and de-duplicated paths.** `replace_paths` order is provider-supplied and providers may emit
duplicate or overlapping paths. Rendering them in arrival order is precisely the failure class of
study defect D2 (five runs, five MD5 hashes) relocated to a new field. Sorting the **formatted**
strings — not the raw step arrays — keeps the rendered order and the sort key identical, so what a
reader sees is what was ordered.

**`[report]` config table, config-only, with strict keys.** The badge opt-out is a repo-level
report-shape preference — the same family as tiers — not a per-invocation override, which is what
every existing CLI flag is (`--show-sensitive`, `--fail-on-critical-on`). A flag would also add an
eighth parameter to `generate()`, and `2026-08-18-fail-on-critical-gate/design.md:122-128` already
records "a tenth option ⇒ revisit the CLI shape" as a standing signal. So: config-only. The new
`ReportOptions` model sets `extra="forbid"`, because an opt-out that silently fails to opt out is
worse than no opt-out — `highlight_unexpected_delete` (missing `s`) must be an error, not a no-op.
Rejected alternative: forbidding unknown keys globally on `PeekConfig`. Rejected as an
unbounded-blast-radius change to every existing config file, made in passing; a mistyped *table*
name (`[reprot]`) therefore still silently no-ops, which is the study's M7 silent-failure family and
stays out of scope — named here so it is a known gap rather than an oversight.

**Default on.** `highlight_unexpected_deletes` defaults to `true`. The badge's whole value is being
there before anyone knew to ask for it; an opt-in accident detector detects no accidents. The
`delete_because_no_resource_config` no-badge case is what keeps the default honest — a badge on every
delete would be decoration.

## Risks / Trade-offs

**[Risk]** The `<summary>` HTML context is a genuinely new escaping surface; a map key containing
`<`, `&` or a newline could corrupt the report structure or inject markup into a PR comment. →
**Mitigation**: a dedicated formatter with the HTML character set handled explicitly, a hostile-map-key
fixture whose key carries `|`, a backtick, a newline and `<b>`, and a golden assertion over the
rendered result. This is the single highest-consequence item in the change and its fixture is
non-optional.

**[Risk]** The `<summary>` path cap could hide the one path a reviewer cared about. → **Mitigation**:
the cap is display-only; the complete, sorted, de-duplicated list is always in the block body, and
the remainder indicator tells the reader more exist. The spec fixes "bounded, with a remainder
indicator", not a specific number, so tuning the number later is not a spec change.

**[Risk]** The reason-phrasing table drifts from Terraform's enum as HashiCorp adds codes. →
**Mitigation**: unknown codes pass through verbatim behind a "reason reported by Terraform" preamble,
and a fixture carrying a deliberately unrecognized `delete_because_*` code pins that path, so drift
degrades a sentence instead of failing a parse or silently dropping the explanation.

**[Risk]** The 💥 badge defaults on, so every repository whose plan contains an addressing-slip delete
sees new, alarming output on upgrade. → **Mitigation**: that is the feature working; the badge fires
only on four specific reason codes that Terraform itself distinguishes from intentional removal, and
`highlight_unexpected_deletes = false` is a one-line opt-out documented in
`docs/reference/configuration.md`.

**[Risk]** Both goldens move, and a golden diff is easy to rubber-stamp. → **Mitigation**: unavoidable
regardless of scope, since `kitchen-sink.json:49` and `examples/demo-plan.json:65` already carry
`replace_paths`. `AGENTS.md` already requires reviewing the regenerated `.md` diff like code; the
per-case fixtures listed in `proposal.md — Impact` mean each behaviour also has a targeted assertion
that does not depend on reading the golden carefully.

**[Risk]** Keeping causation under `detail = "summary"` could be read as leaking information the user
asked to suppress. → **Mitigation**: the distinction is values versus metadata — attribute *names*
and reason codes render; no `before`/`after` value does. Sensitive masking is untouched. The new
capability states this explicitly so the intent is reviewable rather than inferred from a template
branch.

**[Risk]** Two formatters (`format_report_value` and the causation formatter) now encode overlapping
escaping knowledge, so a future hardening fix could be applied to one and not the other. →
**Mitigation**: accepted deliberately over a mode-flagged single formatter (see *A dedicated
path/reason formatter*); the shared invariant is pinned behaviourally by hostile-input fixtures on
both surfaces rather than by shared code, which is how `safe-value-rendering` already pins the value
side.

## Migration Plan

Purely additive: two optional plan fields, one new optional config table, additional report content.
A plan with neither `replace_paths` nor `action_reason` renders exactly as it does today. No data
migration, no invocation changes, no exit-code changes. Both goldens are regenerated with
`uv run poe pytest:integration --snapshot-update` **in the same commit** as the change that causes
them, per `commit-and-pr-conventions` rule 1. Rollback is a normal revert; nothing persists outside
the repository.

## Open Questions

- Should `docs/how-to/` gain a task-shaped page ("find out why Terraform is replacing a resource"), or
  is the reference + explanation update enough? Answerable after the rendering exists and can be
  screenshotted; it changes no spec, no approach and no task beyond a doc file.
- The exact `<summary>` path cap (2 vs 3) is left to implementation, since the spec fixes only
  "bounded, with a remainder indicator". Worth revisiting against a real multi-path plan.
