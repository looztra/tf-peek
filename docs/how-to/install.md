# How to Install tf-peek

This guide covers the available methods for installing `tf-peek` into your environment.

## Prerequisites

- Python 3.11 or later
- `pip`, `uv`, or `pipx` available on your `PATH`

---

## Install with pip

```bash
pip install tf-peek
```

## Install with uv

```bash
uv tool install tf-peek
```

`uv tool install` places the `tf-peek` binary in an isolated environment managed by `uv`, keeping it
separate from your project dependencies.

## Install with pipx

```bash
pipx install tf-peek
```

`pipx` installs the tool in its own isolated virtual environment and exposes the `tf-peek` binary on
your `PATH`.

---

## Verify the installation

After installing, confirm that the binary is available:

```bash
tf-peek --version
```

And that the `generate` command is accessible:

```bash
tf-peek generate --help
```

---

## Install a specific version

If you need a specific release:

```bash
pip install tf-peek==0.1.0
# or
uv tool install tf-peek==0.1.0
```

---

## See also

- [Your first Terraform plan report](../tutorial/first-report.md)
- [How to generate a Markdown report](generate-a-report.md)
