# CLI Entry Points and Data Flow

`tf-peek` is a pure CLI tool with no HTTP endpoints. The diagram below shows the single
command entry point and the flow of data through the system.

## CLI Command

```text
tf-peek generate <json_path> [--config <config_file>] [--output <output_file>]
```

| Argument / Option | Description                                                        |
| :---------------- | :----------------------------------------------------------------- |
| `json_path`       | Path to the Terraform plan JSON file (required)                    |
| `--config / -c`   | Path to a `peek_config.toml` override (optional)                   |
| `--output / -o`   | Path for the output Markdown report (optional, defaults to stdout) |

## Data Flow Diagram

```mermaid
flowchart TD
    A([User: tf-peek generate]) --> B[Load PeekConfig\nfrom peek_config.toml]
    A --> C[Read & parse\nTerraform plan JSON]
    B --> D[Filter resource_changes\nignore / summarize rules]
    C --> D
    D --> E[Classify actions\ncreate / update / delete / replace]
    E --> F[Compute attribute diffs\nbefore vs after]
    F --> G[Render Jinja2 template\nreport.md.j2]
    G --> H{output_file?}
    H -- yes --> I[(Write Markdown file)]
    H -- no --> J[Print to stdout via rich]
```

## Internal Module Dependencies

```mermaid
flowchart LR
    main["main.py\n(CLI + orchestration)"]
    models["models.py\n(Pydantic models)"]
    config["config.py\n(configuration)"]
    tmpl["templates/report.md.j2\n(Jinja2 template)"]

    main --> models
    main --> config
    main --> tmpl
```
