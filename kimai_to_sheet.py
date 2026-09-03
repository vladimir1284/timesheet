#!/usr/bin/env python3
"""
Push a month of Kimai timesheet entries into the shared "dajer" Google Sheet,
one tab per month, matching the existing layout: one block per person (name,
header, formula-driven summary row, daily detail rows), stacked with a blank
row between them, plus a team total block at the end.

New tab is created by duplicating the current first tab (treated as the most
recent month's template) so it inherits column widths and number formats
(duration format on the "time" column, currency on "Salario", etc).

Env vars required, on top of the Kimai ones from kimai_export.py:
  GOOGLE_SHEET_ID              spreadsheet ID from the sheet URL (the long id
                                between /d/ and /edit -- NOT the gid)
  GOOGLE_SERVICE_ACCOUNT_JSON  path to a service-account key JSON; that
                                service account must be shared on the sheet
                                as Editor

Per-person hourly rate + display name are not in Kimai (no rate field there)
and come from rates.json (gitignored, payroll data) next to this script:
  {
    "<kimai_username>": {"display_name": "FULL NAME", "hourly_rate": 7},
    ...
  }
Entries for usernames missing from rates.json are skipped with a warning.

Usage:
  python3 kimai_to_sheet.py [YYYY-MM] [--force]
  Month defaults to previous calendar month, same as kimai_export.py.
  --force overwrites the tab's contents if one for that month already exists.
"""

import json
import os
import sys
from collections import OrderedDict

from google.oauth2 import service_account
from googleapiclient.discovery import build

from kimai_export import fetch_all_timesheets, load_dotenv, month_bounds, previous_month

SPANISH_MONTHS = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
]

RATES_PATH = "rates.json"


def load_rates(path=RATES_PATH):
    if not os.path.isfile(path):
        print(f"Missing {path}. See kimai_to_sheet.py docstring for its format.", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def format_duration(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def group_by_user(rows, rates):
    grouped = OrderedDict((u, []) for u in rates)
    unknown = set()
    for r in rows:
        user = r.get("user")
        username = user.get("username") if isinstance(user, dict) else user
        if username not in grouped:
            unknown.add(username)
            continue
        grouped[username].append(r)
    for username in list(grouped):
        if not grouped[username]:
            del grouped[username]
        else:
            grouped[username].sort(key=lambda r: r.get("begin") or "")
    if unknown:
        print(f"Skipped entries for users not in {RATES_PATH}: {', '.join(sorted(unknown))}", file=sys.stderr)
    return grouped


def build_rows(grouped, rates):
    values = []
    summary_rows = []
    for username, entries in grouped.items():
        info = rates[username]
        block_start = len(values) + 1  # 1-based sheet row of the name row
        summary_row_n = block_start + 2
        detail_start_n = block_start + 3
        detail_end_n = detail_start_n + len(entries) - 1

        values.append(["", "", info["display_name"]])
        values.append(["Date", "time", "Task", "Tarifa por hora", "Salario"])
        values.append([
            "",
            f"=SUM(B{detail_start_n}:B{detail_end_n})",
            "",
            info["hourly_rate"],
            f"=B{summary_row_n}*24*D{summary_row_n}",
        ])
        for e in entries:
            date = (e.get("begin") or "")[:10]
            values.append([date, format_duration(e.get("duration") or 0), e.get("description") or ""])
        values.append([])  # blank separator row
        summary_rows.append(summary_row_n)

    total_row_n = None
    if summary_rows:
        values.append(["", "", "TOTAL EQUIPO", "TOTAL DE HORAS", "TOTAL A PAGAR"])
        hours_formula = "=" + "+".join(f"B{r}*24" for r in summary_rows)
        pay_formula = "=" + "+".join(f"E{r}" for r in summary_rows)
        values.append(["", "", "", hours_formula, pay_formula])
        total_row_n = len(values)

    return values, total_row_n


def get_sheet_id_by_title(service, spreadsheet_id, title):
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == title:
            return s["properties"]["sheetId"]
    return None


def unmerge_sheet(service, spreadsheet_id, sheet_id):
    # Templates carry legacy merged cells (e.g. a merged name row) that swallow
    # values written to any but the merge's top-left cell -- strip them so
    # writes land in the exact column we intend.
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"unmergeCells": {"range": {"sheetId": sheet_id}}}]},
    ).execute()


def set_total_row_format(service, spreadsheet_id, sheet_id, total_row_n):
    row_index = total_row_n - 1  # API grid ranges are 0-based
    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index,
                    "endRowIndex": row_index + 1,
                    "startColumnIndex": 3,  # column D: TOTAL DE HORAS
                    "endColumnIndex": 4,
                },
                "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0.00"}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index,
                    "endRowIndex": row_index + 1,
                    "startColumnIndex": 4,  # column E: TOTAL A PAGAR
                    "endColumnIndex": 5,
                },
                "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        },
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": requests}
    ).execute()


def ensure_month_tab(service, spreadsheet_id, title, force):
    existing_id = get_sheet_id_by_title(service, spreadsheet_id, title)
    if existing_id is not None:
        if not force:
            print(f"Tab '{title}' already exists. Pass --force to overwrite it.", file=sys.stderr)
            sys.exit(1)
        unmerge_sheet(service, spreadsheet_id, existing_id)
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range=f"'{title}'"
        ).execute()
        return existing_id

    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    template_sheet_id = meta["sheets"][0]["properties"]["sheetId"]
    resp = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{
            "duplicateSheet": {
                "sourceSheetId": template_sheet_id,
                "insertSheetIndex": 0,
                "newSheetName": title,
            }
        }]},
    ).execute()
    new_sheet_id = resp["replies"][0]["duplicateSheet"]["properties"]["sheetId"]
    unmerge_sheet(service, spreadsheet_id, new_sheet_id)
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=f"'{title}'"
    ).execute()
    return new_sheet_id


def main():
    load_dotenv()
    force = "--force" in sys.argv[1:]
    args = [a for a in sys.argv[1:] if a != "--force"]
    yyyy_mm = args[0] if args else previous_month()

    base_url = os.environ.get("KIMAI_URL", "").rstrip("/")
    kimai_user = os.environ.get("KIMAI_USER")
    kimai_token = os.environ.get("KIMAI_TOKEN")
    spreadsheet_id = os.environ.get("GOOGLE_SHEET_ID")
    key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not all([base_url, kimai_user, kimai_token, spreadsheet_id, key_path]):
        print(
            "Missing KIMAI_URL/KIMAI_USER/KIMAI_TOKEN/GOOGLE_SHEET_ID/GOOGLE_SERVICE_ACCOUNT_JSON env vars.",
            file=sys.stderr,
        )
        sys.exit(1)

    rates = load_rates()
    begin, end = month_bounds(yyyy_mm)
    rows = fetch_all_timesheets(base_url, kimai_user, kimai_token, begin, end)
    grouped = group_by_user(rows, rates)
    if not grouped:
        print("No entries found for known users in that month.", file=sys.stderr)
        sys.exit(1)

    values, total_row_n = build_rows(grouped, rates)

    year, month = (int(x) for x in yyyy_mm.split("-"))
    title = f"{SPANISH_MONTHS[month - 1]} {year}"

    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds)

    sheet_id = ensure_month_tab(service, spreadsheet_id, title, force)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{title}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()

    if total_row_n is not None:
        # Sheets auto-infers a duration [h]:mm:ss display for a formula cell
        # whose inputs are duration-formatted (our B{n}*24 sums), even with no
        # explicit format stored -- pin plain/currency formats so the already-
        # converted-to-hours total doesn't get re-multiplied by 24 on display.
        set_total_row_format(service, spreadsheet_id, sheet_id, total_row_n)

    total_entries = sum(len(v) for v in grouped.values())
    print(f"{total_entries} entries -> tab '{title}'")


if __name__ == "__main__":
    main()
