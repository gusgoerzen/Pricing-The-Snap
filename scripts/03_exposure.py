"""
NFL Injury Risk Project - Exposure Base & Frequency Calculation
=================================================================
Builds the exposure denominator (player-seasons "at risk") for each
position group, then joins it against the claim counts from
02_classify_injuries.py to produce actual frequency rates -- the
core output an actuary would build first in any pricing exercise.

EXPOSURE DEFINITION (policy decision, stated explicitly):
  A player-season counts as exposure if the player was on an NFL
  roster that season in any status EXCEPT 'DEV' (practice-squad-only).
  Practice-squad players are excluded because they aren't under the
  same NFL player contracts / injury-insurance profile this project
  is modeling.

  We deliberately do NOT require a minimum games-played threshold for
  exposure, even though our original Phase 1 notes floated one. A
  games-played filter would incorrectly exclude the very players who
  suffered season-long injuries (the highest-severity claims) -- their
  low/zero games-played is the outcome we're measuring, not a reason
  to drop them from the denominator. This is flagged explicitly below
  by reporting BOTH a broad and a refined exposure count so the
  sensitivity of this choice is visible rather than hidden.

Run: python 03_exposure.py
Reads:  raw_rosters, player_season_claims_skill, player_season_claims_ol
Writes: exposure_frequency table into the same database
"""

import sqlite3
import pandas as pd

DB_PATH = "../data/nfl_injury_project.db"


def log(msg):
    print(f"[exposure] {msg}")


def broad_exposure(conn):
    """Every rostered player-season, excluding practice-squad-only (DEV) rows."""
    q = """
    SELECT position_group, season, player_id, player_name
    FROM raw_rosters
    WHERE position_group IN ('RB','OL','QB') AND status != 'DEV'
    """
    df = pd.read_sql(q, conn)
    # a player can appear more than once per season (team changes, status changes) -- dedupe
    df = df.drop_duplicates(subset=["position_group", "season", "player_id"])
    return df


def refined_exposure_flags(conn):
    """
    Pull games_played + claim classification for RB/QB (keyed on player_id)
    and OL (keyed on player_name, via the id-join built in step 02) so we
    can identify "camp cut, never really at risk" rows to exclude from the
    refined denominator: games_played == 0 AND not classified as any kind
    of claim (i.e., truly never active, not a season-ending injury case).
    """
    skill = pd.read_sql(
        "SELECT position_group, season, player_id, games_played, claim_classification "
        "FROM player_season_claims_skill",
        conn,
    )
    ol = pd.read_sql(
        "SELECT position_group, season, player_id, player_name, games_played, claim_classification "
        "FROM player_season_claims_ol WHERE id_join_matched = 1",
        conn,
    )
    ol = ol[["position_group", "season", "player_id", "games_played", "claim_classification"]]
    return pd.concat([skill, ol], ignore_index=True)


def build_refined_exposure(broad, flags):
    merged = broad.merge(
        flags, on=["position_group", "season", "player_id"], how="left"
    )
    is_claim = merged["claim_classification"].isin(
        ["PTD", "TTD", "pending_immature", "excluded_sub_threshold"]
    )
    never_at_risk = (merged["games_played"].fillna(0) == 0) & (~is_claim)
    refined = merged[~never_at_risk].copy()
    return refined


def main():
    conn = sqlite3.connect(DB_PATH)

    log("Building broad exposure (all rostered player-seasons, excl. practice squad)...")
    broad = broad_exposure(conn)

    log("Pulling games-played/claim flags to build refined exposure...")
    flags = refined_exposure_flags(conn)
    refined = build_refined_exposure(broad, flags)

    broad_counts = broad.groupby(["position_group", "season"]).size().reset_index(name="broad_exposure")
    refined_counts = refined.groupby(["position_group", "season"]).size().reset_index(name="refined_exposure")

    exposure = broad_counts.merge(refined_counts, on=["position_group", "season"], how="left")
    exposure["refined_exposure"] = exposure["refined_exposure"].fillna(0).astype(int)

    # Pull claim counts (PTD/TTD only) by position + season
    skill = pd.read_sql(
        "SELECT position_group, season, claim_classification FROM player_season_claims_skill", conn
    )
    ol = pd.read_sql(
        "SELECT position_group, season, claim_classification FROM player_season_claims_ol "
        "WHERE id_join_matched = 1",
        conn,
    )
    claims = pd.concat([skill, ol], ignore_index=True)
    claims = claims[claims["claim_classification"].isin(["PTD", "TTD"])]
    claim_counts = (
        claims.groupby(["position_group", "season", "claim_classification"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for col in ["PTD", "TTD"]:
        if col not in claim_counts.columns:
            claim_counts[col] = 0

    result = exposure.merge(claim_counts, on=["position_group", "season"], how="left")
    result[["PTD", "TTD"]] = result[["PTD", "TTD"]].fillna(0).astype(int)
    result["ptd_frequency_broad"] = (result["PTD"] / result["broad_exposure"]).round(4)
    result["ttd_frequency_broad"] = (result["TTD"] / result["broad_exposure"]).round(4)
    refined_safe = result["refined_exposure"].astype("float64").replace(0, float("nan"))
    result["ptd_frequency_refined"] = (result["PTD"] / refined_safe).round(4)
    result["ttd_frequency_refined"] = (result["TTD"] / refined_safe).round(4)

    result.to_sql("exposure_frequency", conn, if_exists="replace", index=False)

    log("\nExposure + frequency by position, summed across all 16 seasons:")
    summary = (
        result.groupby("position_group")[["broad_exposure", "refined_exposure", "PTD", "TTD"]]
        .sum()
        .reset_index()
    )
    summary["ptd_freq_broad"] = (summary["PTD"] / summary["broad_exposure"]).round(4)
    summary["ttd_freq_broad"] = (summary["TTD"] / summary["broad_exposure"]).round(4)
    summary["ptd_freq_refined"] = (summary["PTD"] / summary["refined_exposure"]).round(4)
    summary["ttd_freq_refined"] = (summary["TTD"] / summary["refined_exposure"]).round(4)
    print(summary.to_string(index=False))

    conn.close()
    log("\nDone. Wrote exposure_frequency table.")


if __name__ == "__main__":
    main()
