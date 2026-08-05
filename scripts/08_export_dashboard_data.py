"""
NFL Injury Risk Project - Dashboard Data Export
===================================================
Exports clean, Power-BI-ready CSVs from the project database. These are
intentionally a MIX of a granular fact table (for flexible slicing/
filtering inside Power BI) and pre-aggregated summary tables (for quick
visuals without heavy DAX work).

Run: python 08_export_dashboard_data.py
Writes: ../dashboard/data/*.csv
"""

import sqlite3
import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
from pathlib import Path

DB_PATH = "../data/nfl_injury_project.db"
OUT_DIR = Path("../dashboard/data")


def log(msg):
    print(f"[dashboard-export] {msg}")


def export_player_season_data(conn):
    """Granular fact table: one row per player-season. Lets Power BI
    slicers/filters work on position, age band, season, and classification
    without needing DAX to re-derive anything."""
    query = """
    SELECT
        ps.player_id, p.player_name, ps.season, ps.position_group, ps.age_band,
        ps.games_played, ps.expected_games,
        COALESCE(c.claim_classification, 'no_claim') AS claim_classification,
        c.games_missed
    FROM fact_player_seasons ps
    JOIN dim_players p ON p.player_id = ps.player_id
    LEFT JOIN fact_claims c ON c.player_id = ps.player_id AND c.season = ps.season
    WHERE ps.age_band != 'Unknown'
    """
    df = pd.read_sql(query, conn)
    df["is_ptd"] = (df["claim_classification"] == "PTD").astype(int)
    df["is_ttd"] = (df["claim_classification"] == "TTD").astype(int)
    df.to_csv(OUT_DIR / "player_season_data.csv", index=False)
    log(f"player_season_data.csv -> {len(df):,} rows")


def export_exposure_frequency(conn):
    """Pre-aggregated: exposure + claims + frequency by position x age band."""
    query = """
    SELECT
        ps.position_group, ps.age_band,
        COUNT(*) AS exposure,
        SUM(CASE WHEN c.claim_classification = 'PTD' THEN 1 ELSE 0 END) AS ptd_claims,
        SUM(CASE WHEN c.claim_classification = 'TTD' THEN 1 ELSE 0 END) AS ttd_claims
    FROM fact_player_seasons ps
    LEFT JOIN fact_claims c ON c.player_id = ps.player_id AND c.season = ps.season
    WHERE ps.age_band != 'Unknown'
    GROUP BY ps.position_group, ps.age_band
    """
    df = pd.read_sql(query, conn)
    df["ptd_frequency"] = (df["ptd_claims"] / df["exposure"]).round(4)
    df["ttd_frequency"] = (df["ttd_claims"] / df["exposure"]).round(4)
    df.to_csv(OUT_DIR / "exposure_frequency.csv", index=False)
    log(f"exposure_frequency.csv -> {len(df):,} rows")


def export_rating_relativities(conn):
    """Small table: position-level relativities vs. the OL/TTD base class."""
    query = """
    WITH freq AS (
        SELECT position_group,
            ROUND(1.0*SUM("PTD")/SUM(broad_exposure),4) AS ptd_freq,
            ROUND(1.0*SUM("TTD")/SUM(broad_exposure),4) AS ttd_freq
        FROM exposure_frequency GROUP BY position_group
    ),
    base AS (SELECT ttd_freq AS base_rate FROM freq WHERE position_group='OL')
    SELECT f.position_group, f.ptd_freq, f.ttd_freq,
        ROUND(f.ptd_freq/b.base_rate,2) AS ptd_relativity,
        ROUND(f.ttd_freq/b.base_rate,2) AS ttd_relativity
    FROM freq f, base b
    """
    df = pd.read_sql(query, conn)
    df.to_csv(OUT_DIR / "rating_relativities.csv", index=False)
    log(f"rating_relativities.csv -> {len(df):,} rows")


def export_loss_triangle(conn):
    """Loss development triangle: claim inception vs. resolution by cohort year."""
    query = """
    WITH candidates AS (
        SELECT position_group, player_id, season AS injury_season, claim_classification
        FROM fact_claims WHERE claim_classification IN ('PTD','TTD')
    ),
    dev1_check AS (
        SELECT c.injury_season, c.claim_classification,
            CASE WHEN p1.games_played >= 8 THEN 1 ELSE 0 END AS resolved_by_dev1
        FROM candidates c
        LEFT JOIN fact_player_seasons p1
            ON p1.player_id = c.player_id AND p1.season = c.injury_season + 1
    )
    SELECT
        injury_season,
        COUNT(*) AS dev_0_claims_incepted,
        SUM(resolved_by_dev1) AS dev_1_cumulative_resolved,
        SUM(CASE WHEN claim_classification='TTD' THEN 1 ELSE 0 END) AS dev_2_cumulative_resolved
    FROM dev1_check
    GROUP BY injury_season
    ORDER BY injury_season
    """
    df = pd.read_sql(query, conn)
    df["pct_of_final_ttd_resolved_by_dev1"] = (
        df["dev_1_cumulative_resolved"] / df["dev_2_cumulative_resolved"]
    ).round(3)
    df.to_csv(OUT_DIR / "loss_development_triangle.csv", index=False)
    log(f"loss_development_triangle.csv -> {len(df):,} rows")


def export_contract_severity(conn):
    """Per-claim dollar severity (annualized guaranteed money at risk),
    matched to real contracts -- good for a distribution/box-plot visual."""
    query = """
    WITH ranked_contracts AS (
        SELECT c.position_group, c.player_id, c.season, c.claim_classification,
            ct.guaranteed, ct.years,
            ROW_NUMBER() OVER (
                PARTITION BY c.position_group, c.player_id, c.season
                ORDER BY ct.year_signed DESC
            ) AS rn
        FROM fact_claims c
        LEFT JOIN fact_contracts ct
            ON ct.player_id = c.player_id
            AND c.season >= ct.year_signed AND c.season < ct.year_signed + ct.years
        WHERE c.claim_classification IN ('PTD','TTD')
    )
    SELECT position_group, claim_classification, guaranteed*1.0/years AS annual_guaranteed_at_risk_millions
    FROM ranked_contracts WHERE rn = 1 AND guaranteed IS NOT NULL
    """
    df = pd.read_sql(query, conn)
    df.to_csv(OUT_DIR / "contract_severity.csv", index=False)
    log(f"contract_severity.csv -> {len(df):,} rows")


def export_pricing_scenarios(conn):
    """Re-runs the notebook 3 flat-vs-percentage attachment comparison and
    exports it as a small table for a dashboard comparison visual."""
    query = """
    SELECT ps.player_id, ps.season, ps.position_group, p.birth_date,
        c.claim_classification
    FROM fact_player_seasons ps
    JOIN dim_players p ON p.player_id = ps.player_id
    LEFT JOIN fact_claims c ON c.player_id = ps.player_id AND c.season = ps.season
    WHERE ps.age_band != 'Unknown'
    """
    df = pd.read_sql(query, conn)
    df["birth_date"] = pd.to_datetime(df["birth_date"], errors="coerce")
    season_start = pd.to_datetime(df["season"].astype(str) + "-09-01")
    df["age"] = (season_start - df["birth_date"]).dt.days / 365.25
    df = df[df["claim_classification"] != "pending_immature"].copy()
    df["is_ptd"] = (df["claim_classification"] == "PTD").astype(int)
    df["is_ttd"] = (df["claim_classification"] == "TTD").astype(int)
    df = df.dropna(subset=["age"])

    model_ptd = smf.glm(
        'is_ptd ~ C(position_group, Treatment(reference="OL")) + age',
        data=df, family=sm.families.Binomial()
    ).fit()
    model_ttd = smf.glm(
        'is_ttd ~ C(position_group, Treatment(reference="OL")) + age',
        data=df, family=sm.families.Binomial()
    ).fit()

    severity = pd.read_csv(OUT_DIR / "contract_severity.csv")

    np.random.seed(42)

    def simulate(position, age, structure, n_players=50, n_sims=5000):
        X = pd.DataFrame({"position_group": [position], "age": [age]})
        p_ptd = model_ptd.predict(X).iloc[0]
        p_ttd = model_ttd.predict(X).iloc[0]
        probs = [1 - p_ptd - p_ttd, p_ptd, p_ttd]
        ptd_pool = severity[
            (severity.position_group == position) & (severity.claim_classification == "PTD")
        ]["annual_guaranteed_at_risk_millions"].values
        ttd_pool = severity[
            (severity.position_group == position) & (severity.claim_classification == "TTD")
        ]["annual_guaranteed_at_risk_millions"].values
        totals = np.zeros(n_sims)
        zero_ct, total_ct = 0, 0
        for i in range(n_sims):
            outcomes = np.random.choice(["none", "PTD", "TTD"], size=n_players, p=probs)
            book = 0.0
            for o in outcomes:
                if o == "PTD":
                    loss = np.random.choice(ptd_pool)
                elif o == "TTD":
                    loss = np.random.choice(ttd_pool)
                else:
                    continue
                total_ct += 1
                if structure == "flat":
                    payout = min(max(loss - 0.5, 0), 5.0)
                else:
                    payout = min(max(loss - 0.20 * loss, 0), 1.0 * loss)
                if payout == 0:
                    zero_ct += 1
                book += payout
            totals[i] = book
        return probs, totals, (zero_ct / total_ct if total_ct else None)

    rows = []
    for pos, age in [("RB", 23), ("RB", 25), ("RB", 27), ("RB", 31), ("OL", 27), ("QB", 27)]:
        _, flat_totals, flat_zero = simulate(pos, age, "flat")
        _, pct_totals, pct_zero = simulate(pos, age, "pct")
        rows.append({
            "position": pos, "age": age,
            "flat_mean_premium_M": round(flat_totals.mean() / 50, 4),
            "flat_pct_zero_payout": round(flat_zero, 3),
            "pct_structure_mean_premium_M": round(pct_totals.mean() / 50, 4),
            "pct_structure_pct_zero_payout": round(pct_zero, 3),
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "pricing_scenarios.csv", index=False)
    log(f"pricing_scenarios.csv -> {len(out):,} rows")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    export_player_season_data(conn)
    export_exposure_frequency(conn)
    export_rating_relativities(conn)
    export_loss_triangle(conn)
    export_contract_severity(conn)
    export_pricing_scenarios(conn)

    conn.close()
    log("Done. All dashboard CSVs written to ../dashboard/data/")


if __name__ == "__main__":
    main()
