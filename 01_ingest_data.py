"""
NFL Injury Risk Project - Data Ingestion
==========================================
Pulls raw data from nflverse (via nfl_data_py) for 2009-2024 seasons,
filters to RB / OL / QB position groups, normalizes position labels
across sources, and writes everything into a local SQLite database.

Run: python 01_ingest_data.py
Output: ../data/nfl_injury_project.db
"""

import sqlite3
import pandas as pd
import nfl_data_py as nfl

YEARS = list(range(2009, 2025))  # 2009-2024 seasons (16 seasons)
DB_PATH = "../data/nfl_injury_project.db"

# ---------------------------------------------------------------
# Position normalization map
# Different nflverse tables label positions differently.
# We collapse everything to 3 target groups: RB, OL, QB.
# Any position not in this map is dropped at filter time.
# ---------------------------------------------------------------
POSITION_MAP = {
    # Running backs
    "RB": "RB", "HB": "RB", "FB": "RB",
    # Offensive line (both consolidated and split labels seen across tables)
    "OL": "OL", "T": "OL", "G": "OL", "C": "OL",
    "OT": "OL", "OG": "OL", "LT": "OL", "RT": "OL", "LG": "OL", "RG": "OL",
    # Quarterbacks
    "QB": "QB",
}

TARGET_POSITIONS = set(POSITION_MAP.keys())


def normalize_position(series: pd.Series) -> pd.Series:
    return series.map(POSITION_MAP)


def log(msg):
    print(f"[ingest] {msg}")


def pull_injuries():
    log("Pulling injury reports...")
    df = nfl.import_injuries(YEARS)
    df = df[df["position"].isin(TARGET_POSITIONS)].copy()
    df["position_group"] = normalize_position(df["position"])
    log(f"  -> {len(df):,} injury-report rows (RB/OL/QB, {YEARS[0]}-{YEARS[-1]})")
    return df


def pull_rosters():
    log("Pulling seasonal rosters...")
    df = nfl.import_seasonal_rosters(YEARS)
    df = df[df["position"].isin(TARGET_POSITIONS)].copy()
    df["position_group"] = normalize_position(df["position"])
    log(f"  -> {len(df):,} roster rows (RB/OL/QB)")
    return df


def pull_contracts():
    log("Pulling contracts (OverTheCap via nflverse)...")
    df = nfl.import_contracts()
    df = df[df["position"].isin(TARGET_POSITIONS)].copy()
    df["position_group"] = normalize_position(df["position"])
    # contracts table isn't year-filtered by the API; restrict to signing years in range
    df = df[df["year_signed"].between(YEARS[0], YEARS[-1])]
    log(f"  -> {len(df):,} contract rows (RB/OL/QB, signed {YEARS[0]}-{YEARS[-1]})")
    return df


def pull_snap_counts():
    # nfl_data_py only supports snap counts from 2012 onward
    snap_years = [y for y in YEARS if y >= 2012]
    log(f"Pulling snap counts ({snap_years[0]}-{snap_years[-1]}, source limitation excludes 2009-2011)...")
    df = nfl.import_snap_counts(snap_years)
    df = df[df["position"].isin(TARGET_POSITIONS)].copy()
    df["position_group"] = normalize_position(df["position"])
    log(f"  -> {len(df):,} snap-count rows (RB/OL/QB)")
    return df


def pull_seasonal_stats():
    """
    Core performance data source, full 2009-2024 range.
    Includes EPA (Expected Points Added) -- a stronger performance metric
    than raw box-score stats, available for the whole window.
    Covers RB/QB (skill positions); OL has no comparable per-play stat,
    handled separately via snap counts / games started as a proxy.
    """
    log("Pulling core seasonal stats (EPA, yards, etc.) for RB/QB, full 2009-2024 range...")
    df = nfl.import_seasonal_data(YEARS)
    log(f"  -> {len(df):,} seasonal stat rows (all positions, not yet filtered -- position not in this table)")
    return df


def pull_pfr_advstats():
    """
    PFR advanced stats (rush/pass) are only available from 2018 onward.
    Treated as a SUPPLEMENTARY table (extra detail like broken tackles,
    yards after contact) layered on top of the core seasonal_data table,
    not the primary performance source, since it doesn't cover the full window.
    """
    supp_years = [y for y in YEARS if y >= 2018]
    log(f"Pulling PFR advanced stats (rush + pass, {supp_years[0]}-{supp_years[-1]} only "
        f"-- source limitation excludes {YEARS[0]}-{supp_years[0]-1}; RB/QB only, OL has no box-score stats)...")
    rush = nfl.import_seasonal_pfr("rush", supp_years)
    passing = nfl.import_seasonal_pfr("pass", supp_years)
    rush["stat_type"] = "rush"
    passing["stat_type"] = "pass"
    df = pd.concat([rush, passing], ignore_index=True)
    log(f"  -> {len(df):,} advanced-stat rows (RB rushing + QB passing, {supp_years[0]}+ only)")
    return df


def pull_combine():
    log("Pulling combine data...")
    df = nfl.import_combine_data(YEARS)
    df = df[df["pos"].isin(TARGET_POSITIONS)].copy()
    df["position_group"] = normalize_position(df["pos"])
    log(f"  -> {len(df):,} combine rows (RB/OL/QB)")
    return df


def main():
    conn = sqlite3.connect(DB_PATH)

    tables = {
        "raw_injuries": pull_injuries(),
        "raw_rosters": pull_rosters(),
        "raw_contracts": pull_contracts(),
        "raw_snap_counts": pull_snap_counts(),
        "raw_seasonal_stats": pull_seasonal_stats(),  # not position-filtered here; join to rosters downstream to scope to RB/OL/QB
        "raw_pfr_advstats": pull_pfr_advstats(),
        "raw_combine": pull_combine(),
    }

    log("Writing tables to SQLite...")
    for name, df in tables.items():
        df.to_sql(name, conn, if_exists="replace", index=False)
        log(f"  -> wrote {name} ({len(df):,} rows)")

    conn.close()
    log(f"Done. Database at {DB_PATH}")


if __name__ == "__main__":
    main()
