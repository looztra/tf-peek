## Purpose

Ensures the report explains its own verdicts: when a resource is being replaced or deleted, the reader learns why Terraform decided that, using only what the plan states and never an inferred reason.

## ADDED Requirements

### Requirement: Replacements name the attributes that forced them

When a replaced resource's plan change states one or more replacement-forcing attribute paths, the report SHALL present those paths both in the resource's detail block and on the block's collapsed summary line, so a reader who never expands the block still learns why the resource is being replaced.

#### Scenario: Nested attribute forces a replacement

- **WHEN** a replaced resource's change states a single forcing path of `settings`, index `0`, `tier`
- **THEN** its collapsed summary line names that attribute path
- **THEN** its expanded detail block names that attribute path

#### Scenario: Several attributes force one replacement

- **WHEN** a replaced resource's change states two distinct forcing paths
- **THEN** its detail block names both paths

#### Scenario: Non-replace changes state no forcing paths

- **WHEN** a resource is being created, updated or deleted
- **THEN** its detail block contains no replacement-forcing attribute path, even if the change states one
- **THEN** its collapsed summary line contains no replacement-forcing attribute path

### Requirement: Forcing paths render in Terraform attribute-path notation

A rendered forcing path SHALL use the attribute-path notation a Terraform user reads in human-readable plan output: a numeric step SHALL render as a bracketed index, a step whose name is a valid identifier SHALL render as a dotted name, and any other step SHALL render as a bracketed quoted subscript. The first step SHALL NOT be preceded by a separator.

#### Scenario: Path mixes attribute names and a list index

- **WHEN** a forcing path consists of `settings`, index `0`, `tier`
- **THEN** it renders as `settings[0].tier`

#### Scenario: Path step is not a valid identifier

- **WHEN** a forcing path consists of `labels`, `kubernetes.io/role`
- **THEN** the second step renders as a bracketed quoted subscript rather than a dotted name
- **THEN** the rendered path is unambiguous about where the key begins and ends

### Requirement: Forcing paths are ordered and de-duplicated

Rendered forcing paths SHALL appear in ascending lexical order of their rendered form, and repeated paths SHALL appear once. This holds regardless of the order or multiplicity in which the plan states them, so the same plan always produces the same report bytes.

#### Scenario: Plan states paths out of order

- **WHEN** a replaced resource's change states forcing paths in non-lexical order
- **THEN** the report lists them in ascending lexical order of their rendered form

#### Scenario: Plan states the same path twice

- **WHEN** a replaced resource's change states the same forcing path more than once
- **THEN** the report lists that path exactly once

### Requirement: The collapsed summary line carries a bounded number of forcing paths

The collapsed summary line SHALL present a bounded number of forcing paths and a bounded number of characters of them, and when it presents fewer than the total SHALL indicate that further paths exist. A single path exceeding the character bound SHALL be presented truncated rather than omitted, so the line always names something concrete. The complete list SHALL always be present in the expanded detail block, so neither bound withholds information.

#### Scenario: More forcing paths than the summary line presents

- **WHEN** a replaced resource states more forcing paths than the collapsed summary line presents
- **THEN** the collapsed summary line indicates that further paths exist
- **THEN** the expanded detail block lists every forcing path

#### Scenario: One forcing path is longer than the summary line's character bound

- **WHEN** a replaced resource states a forcing path whose rendered form exceeds the character bound
- **THEN** the collapsed summary line presents that path truncated
- **THEN** the expanded detail block presents it in full

### Requirement: Stated change reasons explain what forcing paths do not

When a resource change states a reason, the report SHALL phrase known reasons as neutral descriptions
of the mechanism Terraform reported. The report SHALL NOT infer whether the change was expected,
intentional, accidental or severe. A reason MAY appear without forcing paths, or alongside paths when
it communicates information those paths do not.

#### Scenario: Resource is replaced because it is tainted

- **WHEN** a replaced resource states the reason `replace_because_tainted` and no forcing paths
- **THEN** its collapsed summary line explains that the resource is tainted
- **THEN** the explanation is prose, not the raw reason code

#### Scenario: Resource is replaced because it was requested

- **WHEN** a replaced resource states the reason `replace_by_request` and no forcing paths
- **THEN** its explanation states that the replacement was explicitly requested when the plan was created

#### Scenario: Resource is replaced because of configured triggers

- **WHEN** a replaced resource states the reason `replace_by_triggers` and no forcing paths
- **THEN** its explanation states that configured replacement triggers selected the replacement

#### Scenario: Resource has no corresponding configuration

- **WHEN** a deleted resource states the reason `delete_because_no_resource_config`
- **THEN** its explanation states that Terraform found no corresponding resource configuration
- **THEN** the explanation makes no claim about whether the removal was intentional

#### Scenario: Resource for_each key no longer matches

- **WHEN** a deleted resource states the reason `delete_because_each_key`
- **THEN** its explanation states that the resource's `for_each` key no longer matches
- **THEN** the explanation makes no claim about whether the deletion was accidental

### Requirement: Forcing paths suppress only a redundant provider reason

When a change states forcing paths and the reason `replace_because_cannot_update`, the report SHALL
present only the forcing paths because they already identify what the provider cannot update in place.
Any other recognized or unrecognized reason SHALL remain visible alongside forcing paths.

#### Scenario: Change states both paths and a provider-cannot-update reason

- **WHEN** a replaced resource states a forcing path and the reason `replace_because_cannot_update`
- **THEN** the report presents the forcing path
- **THEN** the report does not additionally present the provider-cannot-update reason

#### Scenario: Change states paths and a non-redundant reason

- **WHEN** a replaced resource states a forcing path and a reason other than `replace_because_cannot_update`
- **THEN** the report presents the forcing path
- **THEN** the report also presents the stated reason

### Requirement: Unrecognized change reasons and path steps are surfaced rather than dropped or rejected

Terraform documents change reasons as display hints whose set may grow. An unrecognized reason SHALL
NOT prevent the plan from being read and SHALL NOT be silently discarded: the report SHALL render
successfully and present the reason code as reported by Terraform, marked as such. This requirement
also applies when forcing paths are present. A forcing path step of an unexpected type, and an
explicitly null forcing-path list, SHALL likewise not prevent the plan from being read: losing a
display hint SHALL never cost the whole report.

#### Scenario: Plan states a reason code this version does not recognize

- **WHEN** a deleted resource states a reason code that is not one of the recognized codes
- **THEN** the report renders successfully
- **THEN** the resource's explanation contains the reason code as reported by Terraform
- **THEN** the explanation makes clear that the code is passed through rather than interpreted

#### Scenario: Unknown replacement reason accompanies forcing paths

- **WHEN** a replaced resource states forcing paths and an unrecognized reason code
- **THEN** the report presents both the forcing paths and the reason code as reported by Terraform

#### Scenario: Plan states a forcing-path step of an unexpected type

- **WHEN** a replaced resource states a forcing path containing a step that is neither a name nor an index
- **THEN** the report renders successfully
- **THEN** that step is presented as the plan stated it, rather than as a name or an index it is not

#### Scenario: Plan states an explicitly null forcing-path list

- **WHEN** a resource change states `replace_paths` as null rather than omitting it
- **THEN** the report renders successfully, presenting no forcing path for that resource

### Requirement: A change with no stated cause receives no explanation

When a change states neither forcing paths nor a reason, the report SHALL present no explanation for it. The report SHALL NOT infer, guess or interpolate a cause.

#### Scenario: Replacement states neither paths nor a reason

- **WHEN** a replaced resource states no forcing paths and no reason
- **THEN** its detail block contains no explanation of why it is being replaced
- **THEN** the report renders successfully and the resource's attribute diff is unaffected

### Requirement: Replaced resources state which replacement mechanism Terraform will use

A replacement either destroys the existing object before creating its replacement or creates the replacement first. The report SHALL state which mechanism applies in a replaced resource's detail block. The statement SHALL describe the mechanism only and SHALL NOT assert a consequence such as downtime, because the consequence depends on the resource and is not knowable from the plan.

#### Scenario: Replacement destroys before creating

- **WHEN** a replaced resource's change lists its delete action before its create action
- **THEN** its detail block states that the existing object is destroyed before its replacement is created
- **THEN** the statement asserts no consequence such as downtime or data loss

#### Scenario: Replacement creates before destroying

- **WHEN** a replaced resource's change lists its create action before its delete action
- **THEN** its detail block states that the replacement is created before the existing object is destroyed

#### Scenario: Mechanism does not change how the action is classified or counted

- **WHEN** two replaced resources use opposite replacement mechanisms
- **THEN** both are classified as the `replace` action
- **THEN** both are counted in the same summary and resource-type table rows as before

#### Scenario: Mechanism is absent from the collapsed summary line

- **WHEN** a replaced resource is rendered
- **THEN** its collapsed summary line does not state the replacement mechanism

### Requirement: Explanations survive suppressed value detail

A resource whose rule suppresses attribute value detail SHALL still receive its explanation, its forcing paths and its replacement mechanism. Suppressing detail withholds attribute *values*; a forcing path is an attribute name and a reason is plan metadata, so neither is withheld.

#### Scenario: Summarized resource is being replaced

- **WHEN** a resource whose rule sets value detail to summary is being replaced and states a forcing path
- **THEN** its detail block presents no attribute before/after values
- **THEN** its detail block presents the forcing path and the replacement mechanism

### Requirement: Explanations cannot corrupt report structure or inject markup

An attribute path can contain a map key holding arbitrary text, and a stated reason code is arbitrary text too. Rendered explanations and paths SHALL NOT be able to add a Markdown table column, break a table row across physical lines, close a code span, open or close any element of the report's own HTML, or introduce markup — in every context where the report presents them, the Markdown body as well as the collapsed summary line. Escaping SHALL preserve what the plan stated wherever a context allows it: a character that cannot alter the rendering SHALL NOT be rewritten.

#### Scenario: Path contains a pipe and a line break

- **WHEN** a forcing path contains a map key holding both a pipe character and a line feed
- **THEN** the detail block containing it remains structurally intact, with every table row on one physical line and a consistent number of cell delimiters
- **THEN** the collapsed summary line remains a single line

#### Scenario: Path contains markup and code-span characters

- **WHEN** a forcing path contains a map key holding a backtick and text resembling an HTML tag
- **THEN** the collapsed summary line presents that text as literal content rather than as markup
- **THEN** no code span opened by the report is closed by the key's content

#### Scenario: Stated reason contains markup and an element-closing tag

- **WHEN** a resource change states a reason code holding a line feed, an ampersand, a backtick and text closing one of the report's own HTML elements
- **THEN** the report's HTML elements remain balanced, and the reason renders as literal content in both contexts
- **THEN** the explanation stays on one physical line

### Requirement: Explanations do not weaken sensitive-value protection

A forcing path may name an attribute whose value the report masks. The report SHALL present the named attribute — an attribute name is not its value, and Terraform's own output likewise names a forcing attribute beside a redacted value — while continuing to mask the value. A forcing path that descends *into* a masked value SHALL be reduced to the attribute the report masks, because the keys inside a masked value are part of what the mask covers: a rendered path SHALL NOT name anything the attribute table does not already show. The report SHALL apply the same fail-closed masking policy to paths as it applies to values, rather than a second policy of its own.

#### Scenario: Forcing path names a sensitive attribute

- **WHEN** a replaced resource states a forcing path naming an attribute marked sensitive
- **THEN** the report presents the forcing path
- **THEN** that attribute's before and after values remain masked

#### Scenario: Forcing path descends into a masked value

- **WHEN** a replaced resource states a forcing path naming a key inside an attribute whose value is masked
- **THEN** the report presents the masked attribute's name and not the key inside it
- **THEN** that attribute's before and after values remain masked
