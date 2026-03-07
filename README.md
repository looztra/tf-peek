# tf-peek

`tf-peek` converts Terraform plan JSON files into human-readable Markdown reports, with configurable
resource tiers to highlight critical operations and suppress routine noise.

## Quick start

```bash
uv tool install tf-peek
terraform plan -out=tfplan && terraform show -json tfplan > plan.json
tf-peek generate plan.json
```

## Documentation

Full documentation is in the [`docs/`](docs/README.md) folder, organised using the
[Diataxis](https://diataxis.fr) framework:

| Type                                              | Purpose                                          |
| :------------------------------------------------ | :----------------------------------------------- |
| [Tutorial](docs/tutorial/first-report.md)         | Learn by generating your first report            |
| [How-to guides](docs/how-to/)                     | Step-by-step guides for common tasks             |
| [Reference](docs/reference/)                      | CLI options and configuration file specification |
| [Explanation](docs/explanation/resource-tiers.md) | Understand resource tiers and design decisions   |
