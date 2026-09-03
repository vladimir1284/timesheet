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
python3 kimai_export.py [YYYY-MM] [output.csv]
```
- `.env` is loaded automatically by the script (`load_dotenv`); no need to `source` it. Real env vars, if already set, take precedence.
- `YYYY-MM` optional, defaults to the previous calendar month.
- `output.csv` optional, defaults to `kimai_YYYY-MM.csv`.

There is no build, lint, or test tooling in this repo (no package manager, no test files).

## Architecture

Everything lives in `kimai_export.py`, a single script with no dependencies beyond the Python standard library:

1. `load_dotenv` does a minimal `.env` parse into `os.environ` (via `setdefault`, so real env vars win) — no `python-dotenv` dependency.
2. `month_bounds` turns a `YYYY-MM` argument into `begin`/`end` ISO timestamps covering the full calendar month.
3. `fetch_all_timesheets` pages through Kimai's `/api/timesheets` endpoint (`PAGE_SIZE = 100`, `user=all` to include every user's entries — not just the token owner's), following the standard `page`/`size` pagination pattern until a short page or a 404 (interpreted as "past the last page") is hit.
4. `write_csv` flattens each timesheet entry to `date`, `user`, `duration_seconds`, `description` and writes them out.

Auth is sent as `Authorization: Bearer <KIMAI_TOKEN>`. Note: the module docstring says Kimai's legacy scheme (`X-AUTH-USER` + `X-AUTH-TOKEN`) is possible on some instances — if a target Kimai instance rejects the Bearer token, check that instance's `/api/doc` (Swagger) and switch header schemes accordingly. `KIMAI_USER` is currently read from the environment but unused by the request itself.

`user=all` requires the API token's Kimai user to hold a role with "view other timesheet" permission (teamlead/admin) — otherwise Kimai may 403 or silently return only the caller's own entries, depending on version.
