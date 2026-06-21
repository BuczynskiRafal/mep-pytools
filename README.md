# Fast Connect MEP (pyRevit)

A pyRevit add-in that connects MEP elements. Pick two pipes or fittings and it lines them up and joins them.

![icon](assets/icon.png)

## Usage

Open the **MEP Tools** tab on the ribbon and click **Fast Connect**. Pick the element that should stay in place, then the one to move. The add-in finds the nearest matching free connectors, moves and rotates the second element so they meet, and connects them. It runs as a single transaction, so one Ctrl+Z undoes the whole thing.

## Install

Install [pyRevit](https://pyrevitlabs.io), then register this extension:
**pyRevit → Settings → Custom Extension Directories** → add the repo root (the folder containing `MepTools.extension`) → **Save Settings** → **Reload**.

## Tests

```bash
pytest
```

## Stack

Python, pyRevit, Revit API 2026, pytest.
