# External Services

`tf-peek` does **not** call any external services at runtime.

## Runtime Dependencies (local-only)

All inputs and outputs are local files or standard I/O:

| Input / Output      | Description                                                |
| :------------------ | :--------------------------------------------------------- |
| Terraform plan JSON | A local file produced by `terraform show -json <planfile>` |
| `peek_config.toml`  | Optional local TOML configuration file                     |
| Markdown report     | Written to stdout or a local file (`--output`)             |

## Build / Development Services

The following services are used during development and CI only:

| Service | Purpose                                                    |
| :------ | :--------------------------------------------------------- |
| GitHub  | Source code hosting, CI/CD (GitHub Actions), pull requests |
| PyPI    | Distribution of the `tf-peek` package via `uv` / `pip`     |
