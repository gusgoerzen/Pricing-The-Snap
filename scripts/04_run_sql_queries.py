"""
NFL Injury Risk Project - SQL Query Runner
=============================================
Runs every .sql file in ../sql/ against the project database and
prints the results. Lets the SQL query layer be demonstrated/tested
independent of any BI tool.

Run: python 04_run_sql_queries.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "../data/nfl_injury_project.db"
SQL_DIR = Path("../sql")


def main():
    conn = sqlite3.connect(DB_PATH)
    sql_files = sorted(SQL_DIR.glob("*.sql"))

    if not sql_files:
        print(f"No .sql files found in {SQL_DIR.resolve()}")
        return

    for path in sql_files:
        print("=" * 70)
        print(f"{path.name}")
        print("=" * 70)
        query = path.read_text()
        try:
            df = pd.read_sql(query, conn)
            print(df.to_string(index=False))
        except Exception as e:
            print(f"ERROR running {path.name}: {e}")
        print()

    conn.close()


if __name__ == "__main__":
    main()
