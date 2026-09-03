#!/usr/bin/env python3
"""
Export Kimai timesheets for one month to CSV.

Auth: Kimai API token (Profile > API access token in Kimai UI).
Headers used: X-AUTH-USER + X-AUTH-TOKEN (Kimai legacy/API-token scheme).
VERIFY: some Kimai 2.x instances instead expect "Authorization: Bearer <token>".
Check your instance's /api/doc (Swagger) before first run.

Env vars required:
  KIMAI_URL    e.g. https://kimai.example.com  (no trailing slash)
  KIMAI_USER   Kimai username tied to the API token
  KIMAI_TOKEN  API token value

Usage:
  KIMAI_URL=... KIMAI_USER=... KIMAI_TOKEN=... python3 kimai_export.py [YYYY-MM] [output.csv]
  Month arg optional, defaults to previous calendar month.
"""

import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from calendar import monthrange
from datetime import datetime

PAGE_SIZE = 100


def month_bounds(yyyy_mm):
    year, month = (int(x) for x in yyyy_mm.split("-"))
    last_day = monthrange(year, month)[1]
    begin = f"{year:04d}-{month:02d}-01T00:00:00"
    end = f"{year:04d}-{month:02d}-{last_day:02d}T23:59:59"
    return begin, end


def fetch_all_timesheets(base_url, user, token, begin, end):
    results = []
    page = 1
    while True:
        params = {
            "begin": begin,
            "end": end,
            "size": PAGE_SIZE,
            "page": page,
            "orderBy": "begin",
            "order": "ASC",
            "full": "true",
        }
        url = f"{base_url}/api/timesheets?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "kimai-export-script/1.0")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 404 and page > 1:
                break
            print(f"HTTP {e.code} on page {page}: {body}", file=sys.stderr)
            sys.exit(1)

        if not data:
            break
        results.extend(data)
        if len(data) < PAGE_SIZE:
            break
        page += 1
    return results


def write_csv(rows, path):
    fields = ["date", "user", "duration_seconds", "description"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "date": r.get("begin"),
                    "user": (r.get("user") or {}).get("username")
                    if isinstance(r.get("user"), dict)
                    else r.get("user"),
                    "duration_seconds": r.get("duration"),
                    "description": r.get("description"),
                }
            )


def previous_month():
    today = datetime.now()
    year, month = today.year, today.month - 1
    if month == 0:
        year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"


def main():
    yyyy_mm = sys.argv[1] if len(sys.argv) > 1 else previous_month()
    try:
        datetime.strptime(yyyy_mm, "%Y-%m")
    except ValueError:
        print("Month must be YYYY-MM, e.g. 2026-08", file=sys.stderr)
        sys.exit(1)

    out_path = sys.argv[2] if len(sys.argv) > 2 else f"kimai_{yyyy_mm}.csv"

    base_url = os.environ.get("KIMAI_URL", "").rstrip("/")
    user = os.environ.get("KIMAI_USER")
    token = os.environ.get("KIMAI_TOKEN")
    if not all([base_url, user, token]):
        print("Missing KIMAI_URL / KIMAI_USER / KIMAI_TOKEN env vars.", file=sys.stderr)
        sys.exit(1)

    begin, end = month_bounds(yyyy_mm)
    rows = fetch_all_timesheets(base_url, user, token, begin, end)
    write_csv(rows, out_path)
    print(f"{len(rows)} entries -> {out_path}")


if __name__ == "__main__":
    main()
