"""
NFL Injury Risk Project - Injury Episode Classification
=========================================================
Turns raw weekly injury-report data into season-level injury "claims"
classified as PTD / TTD / Excluded, per the project's policy definition:

  Excluded  : games missed due to injury < 2 in the season
  (gap)     : 2-5 games missed -- below the TTD threshold, tracked
              separately as "sub_threshold" rather than silently dropped
  TTD       : 6+ games missed in a season, injury-flagged, AND player
              returns to an active NFL roster within ~18 months
              (approximated here as within 2 subsequent seasons)
              playing 8+ games in a return season
  PTD       : 6+ games missed, injury-flagged, AND no such return
              observed within 2 subsequent seasons

NOTE ON APPROXIMATION LEVEL: this classifies at the PLAYER-SEASON level
(matching the player-season exposure base chosen earlier), not exact
game-by-game injury episodes. This is a deliberate scope decision given
data constraints -- see README/limitations for the full rationale.

Run: python 02_classify_injuries.py
Reads:  ../data/nfl_injury_project.db (raw_* tables)
Writes: player_season_claims table into the same database
"""

import sqlite3
import pandas as pd

DB_PATH = "../data/nfl_injury_project.db"

LAST_COMPLETE_SEASON = 2022  # need 2 subsequent seasons of data to classify -> 2023/2024 are "immature"
RETURN_WINDOW_SEASONS = 2    # how many seasons ahead we check for a "return"
RETURN_GAMES_THRESHOLD = 8   # games played in a season to count as a genuine return, not a token appearance


def log(msg):
    print(f"[classify] {msg}")


def games_played_skill(conn):
    """Games played per player-season for RB/QB, from core seasonal stats."""
    q = """
    SELECT s.player_id, s.season, s.games AS games_played, r.position_group
    FROM raw_seasonal_stats s
    JOIN raw_rosters r ON r.player_id = s.player_id AND r.season = s.season
    WHERE r.position_group IN ('RB','QB')
    """
    df = pd.read_sql(q, conn)
    return df


def games_played_ol(conn):
    """
    Games played per player-season for OL, from snap counts (distinct weeks
    with offense_snaps > 0). Only available 2012+ -- 2009-2011 OL seasons
    cannot be classified this way and are excluded with a flag.
    """
    q = """
    SELECT sc.player AS player_name, sc.season, sc.position, sc.week, sc.offense_snaps
    FROM raw_snap_counts sc
    WHERE sc.position IN ('T','G','C','OL')
    """
    raw = pd.read_sql(q, conn)
    raw["played_week"] = raw["offense_snaps"] > 0
    agg = (
        raw.groupby(["player_name", "season"])["played_week"]
        .sum()
        .reset_index()
        .rename(columns={"played_week": "games_played"})
    )
    agg["position_group"] = "OL"
    agg["data_source"] = "snap_counts"
    return agg


def expected_games(season: int) -> int:
    return 17 if season >= 2021 else 16


def injury_flagged_seasons(conn):
    """Player-seasons with at least one 'Out' or 'Doubtful' weekly designation."""
    q = """
    SELECT gsis_id AS player_id, season, position_group,
           MAX(CASE WHEN report_status IN ('Out','Doubtful') THEN 1 ELSE 0 END) AS injury_flag
    FROM raw_injuries
    GROUP BY gsis_id, season, position_group
    """
    return pd.read_sql(q, conn)


def classify_row(games_missed, injury_flag, has_return_data, returned):
    if injury_flag == 0 or games_missed < 2:
        return "excluded_no_claim"
    if games_missed < 6:
        return "excluded_sub_threshold"
    # games_missed >= 6 and injury-flagged -> candidate claim
    if not has_return_data:
        return "pending_immature"  # too recent to know the outcome yet
    return "TTD" if returned else "PTD"


def build_skill_claims(conn):
    log("Building player-season games-missed table for RB/QB...")
    gp = games_played_skill(conn)
    gp["expected_games"] = gp["season"].apply(expected_games)
    gp["games_missed"] = (gp["expected_games"] - gp["games_played"]).clip(lower=0)

    inj = injury_flagged_seasons(conn)
    merged = gp.merge(
        inj[["player_id", "season", "injury_flag"]],
        on=["player_id", "season"],
        how="left",
    )
    merged["injury_flag"] = merged["injury_flag"].fillna(0).astype(int)

    # build lookup: did the player play >= RETURN_GAMES_THRESHOLD games in season+1 or season+2?
    played_lookup = gp.set_index(["player_id", "season"])["games_played"].to_dict()

    def returned_within_window(player_id, season):
        for offset in range(1, RETURN_WINDOW_SEASONS + 1):
            future = played_lookup.get((player_id, season + offset))
            if future is not None and future >= RETURN_GAMES_THRESHOLD:
                return True
        return False

    def has_return_data_check(season):
        return season <= LAST_COMPLETE_SEASON

    merged["has_return_data"] = merged["season"].apply(has_return_data_check)
    merged["returned"] = merged.apply(
        lambda row: returned_within_window(row["player_id"], row["season"]), axis=1
    )
    merged["claim_classification"] = merged.apply(
        lambda row: classify_row(
            row["games_missed"], row["injury_flag"], row["has_return_data"], row["returned"]
        ),
        axis=1,
    )
    merged["data_source"] = "seasonal_stats"
    return merged


def build_ol_claims(conn):
    log("Building player-season games-missed table for OL (via snap counts, 2012+ only)...")
    gp = games_played_ol(conn)
    gp["expected_games"] = gp["season"].apply(expected_games)
    gp["games_missed"] = (gp["expected_games"] - gp["games_played"]).clip(lower=0)

    # Bridge to gsis_id via name+season match against rosters (pfr_id coverage for OL
    # is 0% in the rosters table, so name+season is used instead -- verified ~97.6%
    # match rate during development; the ~2.4% unmatched are dropped with a flag).
    bridge = pd.read_sql(
        "SELECT DISTINCT player_name, season, player_id FROM raw_rosters WHERE position_group='OL'",
        conn,
    )
    merged = gp.merge(
        bridge, left_on=["player_name", "season"], right_on=["player_name", "season"], how="left"
    )
    merged["id_join_matched"] = merged["player_id"].notna()

    inj = injury_flagged_seasons(conn)
    inj_ol = inj[inj["position_group"] == "OL"][["player_id", "season", "injury_flag"]]
    merged = merged.merge(inj_ol, on=["player_id", "season"], how="left")
    merged["injury_flag"] = merged["injury_flag"].fillna(0).astype(int)

    played_lookup = gp.set_index(["player_name", "season"])["games_played"].to_dict()

    def returned_within_window(player_name, season):
        for offset in range(1, RETURN_WINDOW_SEASONS + 1):
            future = played_lookup.get((player_name, season + offset))
            if future is not None and future >= RETURN_GAMES_THRESHOLD:
                return True
        return False

    merged["has_return_data"] = merged["season"] <= LAST_COMPLETE_SEASON
    merged["returned"] = merged.apply(
        lambda row: returned_within_window(row["player_name"], row["season"]), axis=1
    )

    def classify_ol_row(row):
        if not row["id_join_matched"]:
            return "unclassified_no_id_match"
        return classify_row(row["games_missed"], row["injury_flag"], row["has_return_data"], row["returned"])

    merged["claim_classification"] = merged.apply(classify_ol_row, axis=1)
    merged["data_source"] = "snap_counts"
    return merged


def main():
    conn = sqlite3.connect(DB_PATH)

    skill_claims = build_skill_claims(conn)
    ol_claims = build_ol_claims(conn)

    log("Writing player_season_claims_skill (RB/QB) to database...")
    skill_claims.to_sql("player_season_claims_skill", conn, if_exists="replace", index=False)

    log("Writing player_season_claims_ol (OL, partial -- ID join needed) to database...")
    ol_claims.to_sql("player_season_claims_ol", conn, if_exists="replace", index=False)

    log("\nClassification summary (RB/QB):")
    print(
        skill_claims.groupby(["position_group", "claim_classification"])
        .size()
        .reset_index(name="n")
        .to_string(index=False)
    )

    log("\nClassification summary (OL):")
    print(
        ol_claims.groupby(["position_group", "claim_classification"])
        .size()
        .reset_index(name="n")
        .to_string(index=False)
    )

    conn.close()
    log("Done.")


if __name__ == "__main__":
    main()
