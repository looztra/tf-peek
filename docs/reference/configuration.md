# Configuration Reference

`tf-peek` is configured via a TOML file named `peek_config.toml` in the current working directory,
or at any path passed to `--config`.

If the file does not exist, `tf-peek` uses an empty configuration: every resource is classified as
`normal` with `detail = "full"`.

---

## File structure

The configuration file contains an optional array of resource classification rules under the
`[[resources]]` key:

```toml
[[resources]]
match_type = "null_resource"
tier = "silent"

[[resources]]
match_type = "google_sql_database_instance"
tier = "critical"
critical_on = ["delete", "replace", "update"]
```

Each `[[resources]]` entry is a single classification rule.

---

## Resource rule fields

Each rule must contain **exactly one** of `match_type` or `match_pattern`.

| Field           | Type            | Required | Default                 | Description                                                      |
| :-------------- | :-------------- | :------: | :---------------------- | :--------------------------------------------------------------- |
| `match_type`    | string          |    *     | —                       | Exact match against the Terraform resource type                  |
| `match_pattern` | string (regex)  |    *     | —                       | `re.search` pattern matched against the resource address         |
| `tier`          | enum            |    No    | `"normal"`              | Classification tier: `"silent"`, `"normal"`, `"critical"`        |
| `detail`        | enum            |    No    | `"full"`                | Level of detail for normal-tier resources: `"full"`, `"summary"` |
| `critical_on`   | list of strings |    No    | `["delete", "replace"]` | Actions that trigger the 🚨 critical section                      |

*Exactly one of `match_type` or `match_pattern` is required. Providing both or neither is an error.

---

## `match_type`

An exact string match against the Terraform resource type (`rc.type`).

```toml
[[resources]]
match_type = "google_storage_bucket"
tier = "critical"
```

Matches any resource whose type is exactly `google_storage_bucket`, regardless of its module address
or name.

---

## `match_pattern`

A Python `re.search` regular expression matched against the full resource address (`rc.address`).

```toml
[[resources]]
match_pattern = 'module\.prod_stack\..*\.google_container_cluster\.'
tier = "critical"
```

The pattern is validated at configuration load time; an invalid regex causes an error.

---

## `tier`

Controls how a resource appears in the report.

| Value        | Behaviour                                                                                                 |
| :----------- | :-------------------------------------------------------------------------------------------------------- |
| `"normal"`   | Resource appears in the normal details section. This is the default.                                      |
| `"silent"`   | Resource is counted in the summary (🔇 column) and listed in the 🔇 sub-section, but never shown in detail. |
| `"critical"` | Operations listed in `critical_on` are surfaced in the 🚨 Critical Changes section above the summary.      |

---

## `detail`

Applies only to resources with `tier = "normal"` (the default).

| Value       | Behaviour                                                          |
| :---------- | :----------------------------------------------------------------- |
| `"full"`    | Full attribute diff is shown in a collapsible `<details>` block.   |
| `"summary"` | Only the resource address is shown; the attribute diff is omitted. |

`"summary"` is useful for resource types that produce many changes with verbose diffs (such as IAM
binding types) where the attribute detail adds noise.

---

## `critical_on`

Applies only to resources with `tier = "critical"`.

A list of action strings. When a critical resource performs one of these actions, the resource entry
is moved from the normal details section to the 🚨 Critical Changes section.

Accepted values: `"create"`, `"update"`, `"delete"`, `"replace"`.

Default: `["delete", "replace"]`.

```toml
[[resources]]
match_type = "google_sql_database_instance"
tier = "critical"
critical_on = ["delete", "replace", "update"]
```

When a critical resource performs an action **not** in `critical_on`, it appears in the normal details
section instead.

---

## Rule resolution order

When classifying a resource, `tf-peek` applies rules in the following order:

1. All `match_pattern` rules are evaluated in configuration file order. The first match wins.
2. All `match_type` rules are evaluated in configuration file order. The first match wins.
3. If no rule matches, the default rule is applied: `tier = "normal"`, `detail = "full"`,
   `critical_on = ["delete", "replace"]`.

Rules earlier in the file take precedence within each group. `match_pattern` rules always take
precedence over `match_type` rules regardless of their position in the file.

---

## Full example

```toml
# Silence infrastructure plumbing resources
[[resources]]
match_type = "null_resource"
tier = "silent"

[[resources]]
match_type = "random_id"
tier = "silent"

[[resources]]
match_type = "random_password"
tier = "silent"

[[resources]]
match_type = "time_rotating"
tier = "silent"

# Surface storage and database operations as critical
[[resources]]
match_type = "google_storage_bucket"
tier = "critical"

[[resources]]
match_type = "google_sql_database_instance"
tier = "critical"
critical_on = ["delete", "replace", "update"]

# Silence noisy module-specific null_resources via address pattern
[[resources]]
match_pattern = 'module\.k8s_infra_git_sync\.null_resource\.'
tier = "silent"

# Summarise verbose IAM binding types (no diff, title only)
[[resources]]
match_type = "google_project_iam_binding"
detail = "summary"
```

---

## See also

- [CLI reference](cli.md)
- [Resource tiers explained](../explanation/resource-tiers.md)
- [How to silence noisy resource types](../how-to/silence-noisy-resources.md)
- [How to flag critical resources](../how-to/flag-critical-resources.md)
