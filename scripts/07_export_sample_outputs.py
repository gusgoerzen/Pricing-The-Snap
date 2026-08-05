"""
NFL Injury Risk Project - Export Sample SQL Outputs
=======================================================
Runs each analysis query (skips schema/view DDL files) and writes the
result to sql/sample_output/<name>.csv. This lets someone browsing the
GitHub repo see real query results directly, without needing to clone
the repo and run the full ingestion pipeline first.

Run: python 07_export_sample_outputs.py
Writes: ../sql/sample_output/*.csv
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "../data/nfl_injury_project.db"
SQL_DIR = Path("../sql")
OUT_DIR = Path("../sql/sample_output")

SKIP_FILES = {"00_schema.sql", "06_views.sql"}


def log(msg):
    print(f"[export] {msg}")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    for path in sorted(SQL_DIR.glob("*.sql")):
        if path.name in SKIP_FILES:
            continue
        query = path.read_text()
        try:
            df = pd.read_sql(query, conn)
        except Exception as e:
            log(f"ERROR running {path.name}: {e}")
            continue
        out_path = OUT_DIR / (path.stem + ".csv")
        df.to_csv(out_path, index=False)
        log(f"{path.name} -> {out_path.name} ({len(df)} rows)")

    conn.close()
    log("Done.")


if __name__ == "__main__":
    main()
