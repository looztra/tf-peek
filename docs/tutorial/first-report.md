# Your First Terraform Plan Report

In this tutorial you will install `tf-peek`, export a real Terraform plan, and generate your first
Markdown report. By the end you will have seen `tf-peek` produce a formatted report in your terminal
and saved it to a file.

You do not need any prior experience with `tf-peek`. You do need an existing Terraform project and
a working Python 3.11+ environment.

---

## What you will build

You will generate a report like this one:

```markdown
# Terraform Plan Report

## 🚀 Terraform Plan Summary

| Action      | 🚨 Critical | Normal | 🔇 Silent | Total |
| :---------- | :--------: | :----: | :------: | :---: |
| ➕ Create    |            |   3    |          | **3** |
| 🛠️ Update    |            |   1    |          | **1** |
| **Σ Total** |            | **4**  |          | **4** |
```

---

## Step 1 — Install tf-peek

Install `tf-peek` using `pip` (or your preferred Python package manager):

```bash
pip install tf-peek
```

Verify the installation:

```bash
tf-peek --help
```

You should see:

```text
Usage: tf-peek [OPTIONS] COMMAND [ARGS]...
...
Commands:
  generate  Generate a markdown report from a terraform plan JSON.
```

---

## Step 2 — Produce a Terraform plan JSON

`tf-peek` reads the machine-readable JSON export of a Terraform plan.

In your Terraform project directory, create a plan file and export it to JSON:

```bash
terraform plan -out=tfplan
terraform show -json tfplan > plan.json
```

You now have a `plan.json` file that `tf-peek` can read.

> **Note**: The binary plan file (`tfplan`) is only used to produce the JSON. Only `plan.json` is
> needed by `tf-peek`.

---

## Step 3 — Generate your first report

Run the `generate` command, passing `plan.json` as the argument:

```bash
tf-peek generate plan.json
```

`tf-peek` prints the Markdown report directly to your terminal. Notice the summary table at the top
that lists how many resources are being created, updated, deleted, or replaced.

Below the summary you will find collapsible details for each resource showing the attribute diff —
what changes between the current state and the planned state.

---

## Step 4 — Save the report to a file

To save the report instead of printing it, use the `--output` option:

```bash
tf-peek generate plan.json --output report.md
```

You should see:

```text
Report written to report.md
```

Open `report.md` in any Markdown viewer. On GitHub, you can paste its contents directly into a pull
request description for easy plan review.

---

## What you have done

You have:

1. Installed `tf-peek`.
2. Exported a Terraform plan to JSON using `terraform show -json`.
3. Generated a Markdown report and printed it to the terminal.
4. Saved the report to a file.

---

## Where to go next

- Learn how to reduce noise in your reports by
  [silencing resource types that change on every apply](../how-to/silence-noisy-resources.md).
- Learn how to make critical operations impossible to miss by
  [flagging critical resources](../how-to/flag-critical-resources.md).
- See the full list of options in the [CLI reference](../reference/cli.md).
