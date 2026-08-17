## Context

See `proposal.md` for motivation. `calculate_diff` currently compares only top-level attributes, substitutes only a top-level `after_unknown: true`, and passes raw Python values to the Jinja template. The template stringifies those values separately in six table-cell locations. That creates invalid Markdown for pipes and physical newlines, emits Python `repr` for containers, and loses nested unknown markers.

Existing sensitive-value masking deliberately replaces an entire top-level attribute when any marker in its sensitivity subtree is truthy. That security boundary must remain before any new value formatting.

## Goals / Non-Goals

**Goals:**
- Establish one presentation boundary for every before/after value inserted into a report details table.
- Preserve concrete nested values while representing nested unknown leaves.
- Produce valid Markdown table rows for arbitrary scalar text.
- Keep report output deterministic.

**Non-Goals:**
- Flatten nested changes into path-level diff rows.
- Add resource-type-specific renderers, width truncation, new CLI flags, or output formats.
- Change tier classification, report grouping, or the meaning of `--show-sensitive`.

## Decisions

### Resolve unknown markers before formatting

Add a recursive transformation over an `after` value and its shape-mirroring `after_unknown` marker.

- A marker of `true` replaces that position with the existing known-after-apply display sentinel.
- A marker of `false` retains the concrete value.
- Object markers recurse by key and include keys that exist only in the marker, so unknown-only properties are not omitted.
- List markers recurse by index; a truthy element marker replaces that element, while object markers inside an element recurse normally.
- Use deterministic object-key ordering where the transformation creates a merged object.

This leaves the top-level diff model unchanged: one changed top-level Terraform attribute still produces one report row. It resolves the correctness defect without prematurely adopting the later path-level diff design.

### Format values once, after masking

Keep diff calculation responsible for semantic comparison and sensitivity masking. After those steps, pass each cell value through one canonical formatter before template rendering.

- Preserve `(sensitive value)` and `(known after apply) ⏳` as human-readable display sentinels.
- Render dicts and lists as compact JSON, using JSON literals such as `null`, `true`, and `false` rather than Python `repr`.
- Normalize scalar line endings into visible escaped line-break notation rather than physical newlines.
- Escape Markdown table delimiters after serialization so a `|` remains data, not a cell boundary.

Formatting after masking is non-negotiable: serializing first would create an alternate path that could expose sensitive values. A single formatter prevents the critical and normal report sections from drifting because they share table structure but are rendered by separate template blocks.

### Keep the template presentation-only

Prepare formatted display strings before Jinja rendering, then have every details-table branch print those strings directly. Do not replicate JSON serialization or Markdown escaping in Jinja filters or individual template branches; duplication would make the critical and normal sections diverge.

## Risks / Trade-offs

- Recursive `after_unknown` shapes vary across Terraform values, especially lists. Tests must cover scalar, object, list, and marker-only nested properties; malformed or unexpected marker shapes should not prevent a report from rendering.
- JSON text may be less visually compact than the current Python-style display, but it is portable, unambiguous, and valid for copy/paste.
- Escaping controls makes the source Markdown safer; rendered Markdown viewers may choose their own visual treatment for escape notation.
- The contract intentionally retains top-level blob rows. Path-level diffing remains a separate P1 design so this change does not conflate correctness and reviewer-experience work.
