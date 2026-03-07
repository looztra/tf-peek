# How to Silence Noisy Resource Types

Some Terraform resource types — such as `null_resource`, `random_id`, or `time_rotating` — change on
almost every apply but carry no meaningful information for reviewers. This guide shows you how to
silence them so they are counted in the summary but never shown in detail.

## Prerequisites

- `tf-peek` installed
- A `peek_config.toml` file in your project (create one if it does not exist)

---

## Mark a resource type as silent

Add an entry to your `peek_config.toml` with `tier = "silent"` and `match_type` set to the exact
Terraform resource type you want to silence:

```toml
[[resources]]
match_type = "null_resource"
tier = "silent"

[[resources]]
match_type = "random_id"
tier = "silent"

[[resources]]
match_type = "time_rotating"
tier = "silent"
```

Silent resources are:

- **Counted** in the summary table under the 🔇 Silent column.
- **Listed by type** in a dedicated 🔇 sub-section of the "Changes by Resource Type" table.
- **Never shown** in the detail sections — no diffs, no collapsible entries.

---

## Silence resources matching an address pattern

If you want to silence a subset of instances of a type (for example only those inside a specific
module), use `match_pattern` with a regular expression matched against the full resource address:

```toml
[[resources]]
match_pattern = 'module\.k8s_infra_git_sync\.null_resource\.'
tier = "silent"
```

`match_pattern` takes priority over `match_type` rules. See the
[configuration reference](../reference/configuration.md) for the full resolution order.

---

## Verify the result

Run the report and check the summary table. Silent resources no longer appear in the detail sections
but their count appears under the 🔇 column and the 🔇 sub-section of the type table is visible.

---

## See also

- [Configuration reference](../reference/configuration.md)
- [Resource tiers explained](../explanation/resource-tiers.md)
- [How to flag critical resources](flag-critical-resources.md)
