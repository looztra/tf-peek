## Context

See `proposal.md` for the motivation. `calculate_diff` builds the changed-property union from `before`, `after`, and `after_unknown` keys, then inserts each changed entry into a dictionary. The report template renders that dictionary through `.items()` in every details-table variant, so the insertion order of the diff dictionary becomes visible Markdown order.

The report's other ordered structures are already derived from stable sources for a fixed input: `action_order` is explicit, resource lists follow the parsed plan list, and Python's stable sorting preserves that deterministic input order for equal resource-type counts. The key-union `set` is the only identified hash-order traversal in the report path.

## Goals / Non-Goals

**Goals:**
- Make property-row order deterministic at the point it enters the diff dictionary.
- Preserve current action order, resource order, resource-type count priority, and report content.
- Retain both existing D2 tests as the regression contract, changing their expectation from known failure to required success.

**Non-Goals:**
- Introduce a user-configurable ordering policy.
- Sort Terraform resource changes, addresses, or equal-count resource types beyond their current input-derived order.
- Change rendering, escaping, structured-value formatting, or nested unknown semantics; those remain separate D3–D5 work.

## Decisions

### D1. Sort the complete changed-property union lexically before diff construction

The renderer will traverse the union of `before`, `after`, and `after_unknown` property names in ascending lexical order. This gives every resource-details table the same deterministic order because the template consumes the constructed diff dictionary in insertion order.

Sorting only `before` or `after` would omit properties present exclusively in another input. Sorting in the template would duplicate the policy across the create, delete, update, normal, and critical branches. Ordering at diff construction establishes one policy for all report paths.

### D2. Preserve existing ordering for collections that originate from the plan input

The audit will verify that report-visible collection traversal is either explicitly ordered, produced by a stable sort, or follows the parsed plan's list order. Collections that already meet that condition will not be re-sorted.

A blanket sort of resources or resource-type ties would be an unnecessary observable presentation change and could obscure Terraform's original plan order. The deterministic-output guarantee is for identical inputs, not a new global presentation policy.

### D3. Prove determinism at process and unit boundaries

The existing subprocess test will render the kitchen-sink fixture with multiple `PYTHONHASHSEED` values and require a single output. Its in-process companion will require sorted diff keys directly. Both strict `xfail` markers will be removed; neither test is replaced or weakened.

The golden report snapshot will be regenerated only if lexical property ordering changes its expected byte sequence.

## Risks / Trade-offs

- **Presentation change:** Attribute rows may move relative to reports emitted by prior releases. This is intentional and is limited to deterministic lexical ordering.
- **Incomplete audit risk:** A future unordered collection could reintroduce non-determinism outside property rows. The process-level regression test protects the representative fixture; new report-producing paths must retain explicit or input-stable ordering.
- **Unicode lexical order:** Python's normal string ordering defines the policy. Terraform attribute names are normally ASCII identifiers, so locale-aware ordering would add complexity without user value.

## Migration Plan

No configuration or persisted-data migration is required. Publish the corrected output behavior, update the golden snapshot if necessary, and mark study item P0.2 complete only after the two D2 tests and the integration suite pass.
