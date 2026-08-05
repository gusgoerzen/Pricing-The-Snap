"""
NFL Injury Risk Project - Build Clean Schema
===============================================
Creates the dim/fact schema (sql/00_schema.sql) and populates it from
the raw_* ingestion tables and the player_season_claims_* tables built
in scripts/01-03. This gives the project a proper modeled layer to
query directly, on top of the messier raw ingestion layer.

Run: python 06_build_clean_schema.py
Reads:  raw_rosters, raw_contracts, player_season_claims_skill/ol
Writes: dim_players, fact_player_seasons, fact_claims, fact_contracts
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "../data/nfl_injury_project.db"
SCHEMA_PATH = "../sql/00_schema.sql"


def log(msg):
    print(f"[schema] {msg}")


def create_schema(conn):
    log("Running DDL (sql/00_schema.sql) -- drops and recreates dim/fact tables...")
    ddl = Path(SCHEMA_PATH).read_text()
    conn.executescript(ddl)
    conn.commit()


def populate_dim_players(conn):
    log("Populating dim_players from raw_rosters...")
    df = pd.read_sql(
        """
        SELECT DISTINCT player_id, player_name, position_group, birth_date
        FROM raw_rosters
        WHERE position_group IN ('RB','OL','QB') AND player_id IS NOT NULL
        """,
        conn,
    )
    # a player could theoretically appear with slightly different birth_date
    # formatting across rows -- keep first non-null occurrence per player_id
    df = df.sort_values("player_id").drop_duplicates(subset=["player_id"], keep="first")
    df.to_sql("dim_players", conn, if_exists="append", index=False)
    log(f"  -> {len(df):,} players")


def build_age_band_lookup(conn):
    """Reuses the same age-band logic as sql/02_frequency_by_age_band.sql,
    computed here in pandas for simplicity when populating fact tables."""
    df = pd.read_sql(
        """
        SELECT position_group, season, player_id, birth_date, status
        FROM raw_rosters
        WHERE position_group IN ('RB','OL','QB') AND status != 'DEV'
        """,
        conn,
    )
    df["birth_date"] = pd.to_datetime(df["birth_date"], errors="coerce")
    season_start = pd.to_datetime(df["season"].astype(str) + "-09-01")
    age = ((season_start - df["birth_date"]).dt.days / 365.25).astype("float")
    df["age_at_season"] = age

    def band(a):
        if pd.isna(a):
            return "Unknown"
        if a <= 24:
            return "<=24"
        if a <= 27:
            return "25-27"
        if a <= 30:
            return "28-30"
        return "31+"

    df["age_band"] = df["age_at_season"].apply(band)
    return df[["position_group", "season", "player_id", "age_band"]].drop_duplicates(
        subset=["player_id", "season"]
    )


def populate_fact_player_seasons(conn):
    log("Populating fact_player_seasons (roster x age band x games played)...")
    age_lookup = build_age_band_lookup(conn)

    skill = pd.read_sql(
        "SELECT position_group, season, player_id, games_played, expected_games "
        "FROM player_season_claims_skill",
        conn,
    )
    ol = pd.read_sql(
        "SELECT position_group, season, player_id, games_played, expected_games "
        "FROM player_season_claims_ol WHERE id_join_matched = 1",
        conn,
    )
    games = pd.concat([skill, ol], ignore_index=True).drop_duplicates(
        subset=["player_id", "season"]
    )

    merged = age_lookup.merge(games, on=["position_group", "season", "player_id"], how="left")
    merged["is_exposed"] = 1
    merged = merged[
        ["player_id", "season", "position_group", "age_band", "games_played", "expected_games", "is_exposed"]
    ]
    merged.to_sql("fact_player_seasons", conn, if_exists="append", index=False)
    log(f"  -> {len(merged):,} player-season rows")


def populate_fact_claims(conn):
    log("Populating fact_claims (PTD/TTD/sub-threshold/pending only, not raw non-claims)...")
    keep = ["PTD", "TTD", "excluded_sub_threshold", "pending_immature"]

    skill = pd.read_sql(
        "SELECT player_id, season, position_group, claim_classification, games_missed "
        "FROM player_season_claims_skill",
        conn,
    )
    ol = pd.read_sql(
        "SELECT player_id, season, position_group, claim_classification, games_missed "
        "FROM player_season_claims_ol WHERE id_join_matched = 1",
        conn,
    )
    claims = pd.concat([skill, ol], ignore_index=True)
    claims = claims[claims["claim_classification"].isin(keep)]
    claims.to_sql("fact_claims", conn, if_exists="append", index=False)
    log(f"  -> {len(claims):,} claim rows ({', '.join(keep)})")


def populate_fact_contracts(conn):
    log("Populating fact_contracts from raw_contracts...")
    df = pd.read_sql(
        """
        SELECT gsis_id AS player_id, position_group, year_signed, years, guaranteed, apy
        FROM raw_contracts
        WHERE position_group IN ('RB','OL','QB')
        """,
        conn,
    )
    df.to_sql("fact_contracts", conn, if_exists="append", index=False)
    log(f"  -> {len(df):,} contract rows")


def create_views(conn):
    log("Creating views (sql/06_views.sql)...")
    ddl = Path("../sql/06_views.sql").read_text()
    conn.executescript(ddl)
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    populate_dim_players(conn)
    populate_fact_player_seasons(conn)
    populate_fact_claims(conn)
    populate_fact_contracts(conn)
    conn.commit()
    create_views(conn)

    log("\nRow counts in new schema:")
    for t in ["dim_players", "fact_player_seasons", "fact_claims", "fact_contracts"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n:,}")

    conn.close()
    log("Done.")


if __name__ == "__main__":
    main()
