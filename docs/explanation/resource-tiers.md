# Resource Tiers

`tf-peek` classifies every resource in a Terraform plan into one of three tiers: **silent**,
**normal**, and **critical**. This document explains what those tiers mean, why they exist, and the
trade-offs involved in the design.

---

## The problem tiers solve

A Terraform plan for a real infrastructure stack can contain dozens or hundreds of resource changes.
Without any filtering, every change — from a production database deletion to a routine
`null_resource` replacement — appears at the same level of prominence. Reviewers must scan the entire
report looking for the changes that actually matter.

Two failure modes emerge:

1. **Alert fatigue** — so many routine changes appear in the report that reviewers stop reading it
   carefully.
2. **Missed critical operations** — a destructive operation on a stateful resource hides in the
   middle of a long report.

Tiers address both problems: they let you suppress noise and amplify danger signals.

---

## The three tiers

### Silent

Silent resources are infrastructure plumbing that changes on nearly every apply and carries no
meaningful information for reviewers. Examples include `null_resource`, `random_id`,
`random_password`, and `time_rotating`.

**What happens**: Silent resources are counted in the summary table's 🔇 column and listed by type in
a 🔇 sub-section of the "Changes by Resource Type" table. They are never shown in detail — no
collapsible entries, no attribute diffs.

**Why count them at all**: Silent disclosure matters. If 47 `null_resource` instances are changing, a
reviewer deserves to know that, even if they do not need to see each diff. The 🔇 count makes the
total visible without adding noise.

### Normal

Normal is the default tier. Resources in this tier appear in the main details section of the report
with their full attribute diff (or a title-only summary if `detail = "summary"` is configured).

**When to use normal**: Any resource that warrants review but is not considered dangerous — for
example, IAM bindings, firewall rules, or Kubernetes deployments.

**The `detail` option**: For resource types that produce verbose diffs with many attributes (such as
IAM binding types), you can set `detail = "summary"` to show only the resource address without the
diff. This reduces visual noise while keeping the resource visible.

### Critical

Critical resources are stateful or otherwise dangerous: production databases, storage buckets,
network peerings, VPN gateways. A delete or replace operation on these resources may be irreversible
or cause significant downtime.

**What happens**: When a critical resource performs an action listed in its `critical_on` list (by
default `delete` and `replace`), its entry is moved from the normal details section to a 🚨 Critical
Changes section that appears **above** the main summary table.

**Why above the summary**: The 🚨 section is the first thing a reviewer sees. It is not possible to
miss a critical destructive operation even when reviewing a long report quickly.

**Actions not in `critical_on`**: If a critical resource performs an action that is not in
`critical_on` — for example, a `create` or `update` on a resource whose `critical_on` is only
`["delete", "replace"]` — that resource appears in the normal details section. This avoids flooding
the 🚨 section with routine operations.

---

## Choosing between tiers

Use this as a guide when deciding which tier to assign a resource type:

| Question                                                          | Tier       |
| :---------------------------------------------------------------- | :--------- |
| Does it change on every apply with no meaningful diff?            | `silent`   |
| Is it a production stateful resource where deletion is dangerous? | `critical` |
| Everything else                                                   | `normal`   |

---

## Rule precedence

Tiers are assigned by rules in `peek_config.toml`. When multiple rules could apply to the same
resource, the following order determines which rule wins:

1. `match_pattern` rules (regex on resource address), evaluated in config file order
2. `match_type` rules (exact match on resource type), evaluated in config file order
3. The built-in default (`tier = "normal"`, `detail = "full"`, `critical_on = ["delete", "replace"]`)

This means a specific address pattern rule can always override a broad type-level rule, which lets
you express intent like: "all `null_resource` instances are silent, except for those in
`module.database_migrations` which are critical."

---

## Design trade-offs

**Three tiers, not N**: The framework uses exactly three tiers because they map onto three distinct
reviewer behaviours: ignore, review, escalate. More tiers would require reviewers to learn and
remember a more complex system.

**`critical_on` instead of all-or-nothing**: Not every operation on a critical resource warrants
escalation. A `create` on a storage bucket is safe; a `delete` is not. `critical_on` gives you
per-action control without needing a separate rule for each action type.

**`match_pattern` over `match_type`**: Type-level rules are easy to write and sufficient for most
cases. But real infrastructure uses nested modules, and sometimes only a subset of instances of a
type is dangerous. `match_pattern` provides the escape hatch without making the common case more
complex.

---

## See also

- [Configuration reference](../reference/configuration.md)
- [How to silence noisy resource types](../how-to/silence-noisy-resources.md)
- [How to flag critical resources](../how-to/flag-critical-resources.md)
