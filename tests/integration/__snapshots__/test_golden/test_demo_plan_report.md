# 🚨 Critical Changes

### ➖ Delete

#### `google_storage_bucket`

<details>
<summary><b>🚨 google_storage_bucket.legacy_assets</b></summary>

*`module.storage.google_storage_bucket.legacy_assets`*

| Property | Value |
| :--- | :--- |
| `force_destroy` | `true` |
| `location` | `"EU"` |
| `name` | `"acme-legacy-assets"` |


</details>

#### `google_compute_network_peering`

<details>
<summary><b>🚨 google_compute_network_peering.to_shared</b></summary>

*`google_compute_network_peering.to_shared`*

| Property | Value |
| :--- | :--- |
| `export_custom_routes` | `false` |
| `name` | `"to-shared-vpc"` |
| `peer_network` | `"projects/acme-shared/global/networks/shared"` |


</details>


### ⚠️ Replace

#### `google_sql_database_instance`

<details>
<summary><b>🚨 google_sql_database_instance.prod</b></summary>

*`google_sql_database_instance.prod`*

| Property | Before | After |
| :--- | :--- | :--- |
| `root_password` | `(sensitive value)` | `(sensitive value)` |
| `settings` | `[{"tier": "db-f1-micro", "availability_type": "ZONAL", "backup_configuration": [{"enabled": true, "retained_backups": 7}]}]` | `[{"tier": "db-custom-4-15360", "availability_type": "REGIONAL", "backup_configuration": [{"enabled": true, "retained_backups": 30}], "ip_address": "(known after apply) ⏳"}]` |


</details>



---

# Terraform Plan Report

## 🚀 Terraform Plan Summary


| Action | 🚨 Critical | Normal | 🔇 Silent | Total |
| :--- | :---: | :---: | :---: | :---: |
| ➖ Delete | ${\color{red}2}$ | 1 |  | **3** |
| ⚠️ Replace | ${\color{red}1}$ |  | 🔇 2 | **3** |
| 🛠️ Update |  | 1 | 🔇 1 | **2** |
| ➕ Create |  | 3 | 🔇 1 | **4** |
| **Σ Total** | **${\color{red}3}$** | **5** | **🔇 4** | **12** |

### Changes by Resource Type

<details>
<summary><b>View changes by Resource Type</b></summary>

| Resource Type | ➖ Delete | ⚠️ Replace | 🛠️ Update | ➕ Create | **Total** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `google_project_iam_member` | ${\color{red}1}$ |  |  | 1 | **2** |
| `google_sql_database_instance` |  | ${\color{orange}1}$ |  |  | **1** |
| `google_storage_bucket` | ${\color{red}1}$ |  |  |  | **1** |
| `google_compute_network_peering` | ${\color{red}1}$ |  |  |  | **1** |
| `google_cloud_run_service` |  |  | 1 |  | **1** |
| `google_compute_firewall` |  |  |  | 1 | **1** |
| `google_secret_manager_secret_iam_member` |  |  |  | 1 | **1** |

---

🔇 *Silent (counted, not detailed)*

| Resource Type | ➖ Delete | ⚠️ Replace | 🛠️ Update | ➕ Create | **Total** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `null_resource` 🔇 |  | 1 |  |  | **1** |
| `random_password` 🔇 |  | 1 |  |  | **1** |
| `random_id` 🔇 |  |  |  | 1 | **1** |
| `time_rotating` 🔇 |  |  | 1 |  | **1** |

</details>

---

## 🔍 Resource Details

### ➖ Delete

#### `google_project_iam_member`

<details>
<summary><b>google_project_iam_member.viewer</b></summary>

*`google_project_iam_member.viewer`*

> ℹ️ *Details hidden by configuration (filtered resource).*


</details>


### 🛠️ Update

#### `google_cloud_run_service`

<details>
<summary><b>google_cloud_run_service.api</b></summary>

*`google_cloud_run_service.api`*

| Property | Before | After |
| :--- | :--- | :--- |
| `image` | `"eu.gcr.io/acme/api:1.4.2"` | `"eu.gcr.io/acme/api:1.5.0"` |
| `min_instances` | `1` | `2` |
| `status` | `null` | `(known after apply) ⏳` |


</details>


### ➕ Create

#### `google_compute_firewall`

<details>
<summary><b>google_compute_firewall.allow_https</b></summary>

*`module.network.google_compute_firewall.allow_https`*

| Property | Value |
| :--- | :--- |
| `id` | `(known after apply) ⏳` |
| `name` | `"allow-https"` |
| `priority` | `1000` |
| `source_ranges` | `["0.0.0.0/0"]` |


</details>

#### `google_project_iam_member`

<details>
<summary><b>google_project_iam_member.ci_deployer</b></summary>

*`google_project_iam_member.ci_deployer`*

> ℹ️ *Details hidden by configuration (filtered resource).*


</details>

#### `google_secret_manager_secret_iam_member`

<details>
<summary><b>google_secret_manager_secret_iam_member.api_db_password</b></summary>

*`google_secret_manager_secret_iam_member.api_db_password`*

> ℹ️ *Details hidden by configuration (filtered resource).*


</details>
