# timesheet

Export Kimai timesheet entries to CSV, as a first step toward syncing them into a Google Sheet.

## Setup

```
cp .env.example .env
# fill in KIMAI_URL, KIMAI_USER, KIMAI_TOKEN
```

Auth uses a Kimai API token (Profile > API access token in the Kimai UI), sent as `Authorization: Bearer <token>`.

## Usage

```
set -a && source .env && set +a
python3 kimai_export.py [YYYY-MM] [output.csv]
```

- `YYYY-MM` is optional; defaults to the previous calendar month.
- `output.csv` is optional; defaults to `kimai_YYYY-MM.csv`.

Output columns: `date`, `user`, `duration_seconds`, `description`.

## Status

Kimai -> CSV extraction works. Google Sheets sync not implemented yet.
