# How to Flag Critical Resources

Resources such as production databases, storage buckets, or network configurations deserve special
attention when they are deleted or replaced. This guide shows you how to surface those operations in a
dedicated 🚨 Critical Changes section at the top of your report.

## Prerequisites

- `tf-peek` installed
- A `peek_config.toml` file in your project (create one if it does not exist)

---

## Mark a resource type as critical

Add an entry to your `peek_config.toml` with `tier = "critical"` and specify the resource type:

```toml
[[resources]]
match_type = "google_storage_bucket"
tier = "critical"
```

By default, only `delete` and `replace` operations on a critical resource are moved to the 🚨 section.
Other actions (`create`, `update`) for the same type appear in the normal details section as usual.

---

## Include more actions in the critical section

To flag additional action types — for example, flagging updates to a stateful resource — set
`critical_on` explicitly:

```toml
[[resources]]
match_type = "google_sql_database_instance"
tier = "critical"
critical_on = ["delete", "replace", "update"]
```

`critical_on` accepts any combination of `"create"`, `"update"`, `"delete"`, and `"replace"`.

---

## Flag resources by address pattern

If you want to flag only specific instances of a type, use `match_pattern`:

```toml
[[resources]]
match_pattern = 'module\.prod_stack\..*\.google_container_cluster\.'
tier = "critical"
critical_on = ["delete", "replace", "update"]
```

`match_pattern` is a Python `re.search` expression matched against the full resource address.

---

## What the report looks like

When a critical operation is detected, the report opens with a 🚨 Critical Changes section:

```markdown
# 🚨 Critical Changes

### ➖ Delete

#### `google_storage_bucket`

<details>
<summary><b>🚨 google_storage_bucket.my_bucket</b></summary>
...
</details>
```

This section appears **above** the main summary table so it is impossible to miss.

---

## See also

- [Configuration reference](../reference/configuration.md)
- [Resource tiers explained](../explanation/resource-tiers.md)
- [How to silence noisy resource types](silence-noisy-resources.md)
