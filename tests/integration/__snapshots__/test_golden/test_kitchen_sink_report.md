# Terraform Plan Report

## 🚀 Terraform Plan Summary


| Action | 🚨 Critical | Normal | 🔇 Silent | Total |
| :--- | :---: | :---: | :---: | :---: |
| ⚠️ Replace |  | 2 |  | **2** |
| 🛠️ Update |  | 1 |  | **1** |
| **Σ Total** |  | **3** |  | **3** |

### Changes by Resource Type

<details>
<summary><b>View changes by Resource Type</b></summary>

| Resource Type | ➖ Delete | ⚠️ Replace | 🛠️ Update | ➕ Create | **Total** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `google_sql_database_instance` |  | ${\color{orange}1}$ |  |  | **1** |
| `google_storage_bucket` |  |  | 1 |  | **1** |
| `google_compute_instance` |  | ${\color{orange}1}$ |  |  | **1** |

</details>

---

## 🔍 Resource Details

### ⚠️ Replace

#### `google_sql_database_instance`

<details>
<summary><b>google_sql_database_instance.prod</b> — forces replacement: <code>settings[0].tier</code></summary>

*`google_sql_database_instance.prod`*

**Forces replacement:** `settings[0].tier`

**Mechanism:** the existing object is destroyed before its replacement is created

| Property | Before | After |
| :--- | :--- | :--- |
| `password` | `(sensitive value)` | `(sensitive value)` |
| `settings` | `[{"tier": "db-f1-micro", "flags": [{"name": "max_connections", "value": "100"}]}]` | `[{"tier": "db-n1-standard-1", "flags": "(known after apply) ⏳", "ip_address": "(known after apply) ⏳"}]` |


</details>

#### `google_compute_instance`

<details>
<summary><b>google_compute_instance.web</b> — forces replacement: <code>machine_type</code>; configured replacement triggers selected the replacement</summary>

*`google_compute_instance.web`*

**Forces replacement:** `machine_type`

**Reason:** configured replacement triggers selected the replacement

**Mechanism:** the replacement is created before the existing object is destroyed

| Property | Before | After |
| :--- | :--- | :--- |
| `machine_type` | `"e2-small"` | `"e2-medium"` |


</details>


### 🛠️ Update

#### `google_storage_bucket`

<details>
<summary><b>google_storage_bucket.docs</b></summary>

*`module.storage.google_storage_bucket.docs`*

| Property | Before | After |
| :--- | :--- | :--- |
| `desc` | `"old description"` | `"has \u007c pipe\nand a newline"` |


</details>
