# Terraform Plan Report

## 🚀 Terraform Plan Summary


| Action | 🚨 Critical | Normal | 🔇 Silent | Total |
| :--- | :---: | :---: | :---: | :---: |
| ⚠️ Replace |  | 1 |  | **1** |
| 🛠️ Update |  | 1 |  | **1** |
| **Σ Total** |  | **2** |  | **2** |

### Changes by Resource Type

<details>
<summary><b>View changes by Resource Type</b></summary>

| Resource Type | ➖ Delete | ⚠️ Replace | 🛠️ Update | ➕ Create | **Total** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `google_sql_database_instance` |  | ${\color{orange}1}$ |  |  | **1** |
| `google_storage_bucket` |  |  | 1 |  | **1** |

</details>

---

## 🔍 Resource Details

### ⚠️ Replace

#### `google_sql_database_instance`

<details>
<summary><b>google_sql_database_instance.prod</b></summary>

*`google_sql_database_instance.prod`*

| Property | Before | After |
| :--- | :--- | :--- |
| `settings` | `[{'tier': 'db-f1-micro', 'flags': [{'name': 'max_connections', 'value': '100'}]}]` | `[{'tier': 'db-n1-standard-1', 'flags': [{'name': 'max_connections', 'value': '100'}]}]` |
| `password` | `(sensitive value)` | `(sensitive value)` |

</details>


### 🛠️ Update

#### `google_storage_bucket`

<details>
<summary><b>google_storage_bucket.docs</b></summary>

*`module.storage.google_storage_bucket.docs`*

| Property | Before | After |
| :--- | :--- | :--- |
| `desc` | `old description` | `has | pipe
and a newline` |

</details>
