# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Single-script tool that exports Kimai timesheet entries for one month to CSV. First step toward eventually syncing timesheet data into a Google Sheet (not implemented yet).

## Commands

Setup:
```
cp .env.example .env
# fill in KIMAI_URL, KIMAI_USER, KIMAI_TOKEN
```

Run:
```
set -a && source .env && set +a
python3 kimai_export.py [YYYY-MM] [output.csv]
```
- `YYYY-MM` optional, defaults to the previous calendar month.
- `output.csv` optional, defaults to `kimai_YYYY-MM.csv`.

There is no build, lint, or test tooling in this repo (no package manager, no test files).

## Architecture

Everything lives in `kimai_export.py`, a single script with no dependencies beyond the Python standard library:

1. `month_bounds` turns a `YYYY-MM` argument into `begin`/`end` ISO timestamps covering the full calendar month.
2. `fetch_all_timesheets` pages through Kimai's `/api/timesheets` endpoint (`PAGE_SIZE = 100`), following the standard `page`/`size` pagination pattern until a short page or a 404 (interpreted as "past the last page") is hit.
3. `write_csv` flattens each timesheet entry to `date`, `user`, `duration_seconds`, `description` and writes them out.

Auth is sent as `Authorization: Bearer <KIMAI_TOKEN>`. Note: the module docstring says Kimai's legacy scheme (`X-AUTH-USER` + `X-AUTH-TOKEN`) is possible on some instances — if a target Kimai instance rejects the Bearer token, check that instance's `/api/doc` (Swagger) and switch header schemes accordingly. `KIMAI_USER` is currently read from the environment but unused by the request itself.

Config is env-var only (`KIMAI_URL`, `KIMAI_USER`, `KIMAI_TOKEN`), loaded via `.env` + `set -a`/`source`/`set +a` — there's no `.env`-parsing library dependency.
