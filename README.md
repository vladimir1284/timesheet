# timesheet

Export Kimai timesheet entries to CSV, as a first step toward syncing them into a Google Sheet.

## Setup

Uses [uv](https://docs.astral.sh/uv/) for the env and deps.

```
uv sync
cp .env.example .env
# fill in KIMAI_URL, KIMAI_USER, KIMAI_TOKEN
```

Auth uses a Kimai API token (Profile > API access token in the Kimai UI), sent as `Authorization: Bearer <token>`.

## Usage

```
uv run kimai_export.py [YYYY-MM] [output.csv]
uv run kimai_to_sheet.py [YYYY-MM]
```

`.env` is loaded automatically; no need to `source` it first.

- `YYYY-MM` is optional; defaults to the previous calendar month.
- `output.csv` is optional; defaults to `kimai_YYYY-MM.csv`.

Output columns: `date`, `user`, `duration_seconds`, `description`.

## Status

Kimai -> CSV extraction works. Kimai -> Google Sheets push works (`kimai_to_sheet.py`).
