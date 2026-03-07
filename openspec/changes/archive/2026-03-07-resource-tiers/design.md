## Context

tf-peek currently classifies resources into three flat categories (`ignore`, `summarize`, default) driven by type-prefix string matching in `PeekConfig`. This works for basic noise reduction but collapses two orthogonal concerns — **importance** (should the user care?) and **detail level** (how much diff to show?) — into a single axis. It also provides no way to highlight genuinely dangerous operations such as database deletions.

The report structure today is: Summary → Changes by Type → Resource Details. There is no top-level alert for high-severity operations and no per-tier breakdown in the summary counts.

## Goals / Non-Goals

**Goals:**
- Introduce three resource tiers (`silent`, `normal`, `critical`) with distinct rendering behaviour
- Support two match strategies: exact type match (`match_type`) and regex pattern match against full address (`match_pattern`)
- Surface critical operations (delete/replace by default, configurable per resource) in a dedicated 🚨 section above the summary
- Disclose silent resources in the "Changes by Resource Type" table without exposing their details
- Extend summary counts with per-tier columns
- Allow `normal` resources to opt into `detail = "summary"` (title only, no diff) replacing the old `summarize` key

**Non-Goals:**
- Module-aware grouping of resources
- Masking of sensitive attribute values
- Runtime `--show-silent` flag or any CLI verbosity control
- Migration tooling for existing `peek_config.toml` files

## Decisions

### D1: Array-of-tables TOML config (`[[resources]]`)

**Decision**: Replace the flat `[filters]` section with a TOML array-of-tables where each entry is a resource rule.

**Rationale**: A flat list of strings (old `ignore = [...]`) cannot carry per-resource metadata (tier, detail level, critical_on). Array-of-tables is idiomatic TOML for heterogeneous rule lists. Each entry has:

```toml
[[resources]]
match_type = "aiven_pg"        # OR match_pattern = "regex"
tier = "critical"              # silent | normal | critical  (default: normal)
detail = "full"                # full | summary              (default: full)
critical_on = ["delete", "replace"]  # critical tier only   (default: ["delete", "replace"])
```

Exactly one of `match_type` or `match_pattern` must be present per entry.

**Alternatives considered**:
- Single `match` key with a `match_mode` field — more verbose, no benefit over two distinct keys
- Separate `[tiers.critical]`, `[tiers.silent]` sections — inflexible, cannot express per-entry `critical_on`

---

### D2: `match_pattern` is a regex matched against `rc.address`

**Decision**: `match_pattern` values are Python `re.search()` patterns tested against the full resource address string.

**Rationale**: Real Terraform addresses contain dynamic module keys with bracket notation (e.g., `module.aiven_postgresql["cfurmaniak-sbox-a2cv-pgsource"].aiven_pg.service`). Glob patterns cannot express "prod module only". Regex is the natural fit and already available in Python stdlib.

**Alternatives considered**:
- Glob matching — insufficient expressiveness for nested module key filtering
- Raw prefix matching — fragile (`aiven_p` matches both `aiven_pg` and `aiven_project_vpc`)

---

### D3: `match_pattern` takes priority over `match_type`; first match wins within each strategy

**Decision**: For a given resource, all `match_pattern` rules are evaluated first (in config order). If none match, `match_type` rules are evaluated (in config order). First match wins.

**Rationale**: Address-level patterns are inherently more specific than type-level patterns. Users writing a `match_pattern` rule for a specific module path expect it to override a general type-level rule.

---

### D4: Critical resources appear **only** in the 🚨 section for their critical operations

**Decision**: A critical resource's operations that are listed in `critical_on` are rendered exclusively in the top 🚨 Critical Changes section. Operations on the same resource that are **not** in `critical_on` are rendered in the normal 🔍 Resource Details section. The resource does **not** appear in both sections for the same operation.

**Rationale**: Duplication creates confusion ("did I already review this?"). Single-location rendering is cleaner. The type table still shows the total counts regardless of where the detail appears.

---

### D5: Silent resources disclosed in the Changes by Resource Type table as a 🔇 sub-section

**Decision**: The type table gains a visual separator and a 🔇 sub-section listing silent resource types with their per-action counts. No details section entry is created for silent resources.

**Rationale**: The user needs to know silent resources exist and how many changed (Option 3 from exploration). A sub-section in the type table is less intrusive than adding rows to the summary table but more informative than a footer footnote.

---

### D6: Summary table extended with per-tier count columns

**Decision**: The summary table replaces the single `Count` column with three columns: `🚨 Critical | Normal | 🔇 Silent`. Total column retained.

**Rationale**: Gives the user an immediate at-a-glance sense of how many changes are routine vs. dangerous vs. suppressed, without drilling into the details.

---

### D7: `detail = "summary"` replaces old `summarize` config key

**Decision**: The old `summarize` list is removed. Resources that previously lived in `summarize` are now expressed as `tier = "normal"`, `detail = "summary"` rules.

**Rationale**: Keeps the concept (show title, hide diff) but embeds it in the unified rule model rather than a parallel config key.

## Risks / Trade-offs

- **Regex misconfiguration** → A badly written `match_pattern` could silently fail to match intended resources, causing them to fall through to `normal` tier. Mitigation: clear documentation and example patterns; future tooling (linting) is out of scope.
- **Config migration burden** → Existing `peek_config.toml` files break on upgrade (BREAKING change). Mitigation: document migration in CHANGELOG and README; sample config is updated; no automated migration tool provided.
- **Regex injection not a concern** → `match_pattern` is evaluated only against locally-sourced Terraform plan data; no external input surfaces through the pattern evaluation path.
- **First-match-wins ordering sensitivity** → Rule order matters; a general rule placed before a specific one will shadow it. Mitigation: document clearly; specific rules should be placed before general ones.

## Migration Plan

1. Update `config.toml` sample to new `[[resources]]` schema
2. Update `PeekConfig` and `load_config()` — old keys simply won't load (Pydantic will ignore unknown keys or raise; choose strict validation)
3. Update rendering pipeline in `main.py`
4. Update Jinja2 template
5. Update tests

No database or state migrations. No deployment coordination needed (CLI tool, local execution).

## Open Questions

- Should `load_config()` raise a hard error on unknown top-level TOML keys (strict) or silently ignore them (lenient)? Strict is safer for catching stale configs.
- Should a resource matched by both `match_type` AND `match_pattern` rules from different entries ever warn the user? (Proposed: no, silent first-match-wins is simpler.)
