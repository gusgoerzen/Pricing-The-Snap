-- =============================================================
-- 03_severity_by_classification.sql
-- Business question: "When a claim happens, how bad is it? Does
-- severity (games missed) differ between TTD, PTD, and the
-- sub-threshold tier, and does that differ by position?"
--
-- This is the severity half of the frequency/severity split --
-- frequency answers "how often," this answers "how bad."
-- =============================================================

WITH all_claims AS (
    SELECT position_group, claim_classification, games_missed, games_played, expected_games
    FROM player_season_claims_skill
    UNION ALL
    SELECT position_group, claim_classification, games_missed, games_played, expected_games
    FROM player_season_claims_ol
    WHERE id_join_matched = 1
)
SELECT
    position_group,
    claim_classification,
    COUNT(*)                       AS n,
    ROUND(AVG(games_missed), 2)    AS avg_games_missed,
    MIN(games_missed)              AS min_games_missed,
    MAX(games_missed)              AS max_games_missed
FROM all_claims
WHERE claim_classification IN ('PTD', 'TTD', 'excluded_sub_threshold')
GROUP BY position_group, claim_classification
ORDER BY
    position_group,
    CASE claim_classification
        WHEN 'excluded_sub_threshold' THEN 1
        WHEN 'TTD' THEN 2
        WHEN 'PTD' THEN 3
    END;
