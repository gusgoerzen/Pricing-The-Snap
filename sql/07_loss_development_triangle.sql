-- =============================================================
-- 07_loss_development_triangle.sql
-- A loss development triangle: for each injury cohort year
-- ("accident year" in P&C terms), how many candidate claims (PTD or
-- TTD) were incepted, and how many had been resolved (returned to
-- play, i.e., TTD) by 1 season later (dev_1) and by 2 seasons later
-- (dev_2, which equals the final TTD count under this project's
-- classification rule).
--
-- This is the same underlying pattern real reserving actuaries use
-- to track how claims develop/settle over time -- here applied to
-- "does the player return to play" instead of "is the claim paid."
--
-- Cohorts are naturally limited to injury_season <= 2022, since 2023+
-- seasons are still "pending_immature" in fact_claims (not yet old
-- enough to have a final TTD/PTD outcome) and are correctly excluded
-- by the claim_classification filter below.
-- =============================================================

WITH candidates AS (
    SELECT position_group, player_id, season AS injury_season, claim_classification
    FROM fact_claims
    WHERE claim_classification IN ('PTD', 'TTD')
),
dev1_check AS (
    SELECT
        c.injury_season,
        c.claim_classification,
        CASE WHEN p1.games_played >= 8 THEN 1 ELSE 0 END AS resolved_by_dev1
    FROM candidates c
    LEFT JOIN fact_player_seasons p1
        ON p1.player_id = c.player_id AND p1.season = c.injury_season + 1
)
SELECT
    injury_season,
    COUNT(*)                                                          AS dev_0_claims_incepted,
    SUM(resolved_by_dev1)                                             AS dev_1_cumulative_resolved,
    SUM(CASE WHEN claim_classification = 'TTD' THEN 1 ELSE 0 END)     AS dev_2_cumulative_resolved,
    ROUND(1.0 * SUM(resolved_by_dev1) /
        SUM(CASE WHEN claim_classification = 'TTD' THEN 1 ELSE 0 END), 3
    )                                                                  AS pct_of_final_ttd_resolved_by_dev1
FROM dev1_check
GROUP BY injury_season
ORDER BY injury_season;
