-- =============================================================
-- 04_dollar_exposure_by_classification.sql
-- Business question: "When a claim happens, how much guaranteed
-- contract money is actually at risk?" -- the dollar-severity
-- view a real pricing exercise needs, not just games missed.
--
-- Each claim season is matched to the contract that was active
-- for that player in that season (year_signed <= season <
-- year_signed + years). A player can have more than one contract
-- on file that could technically overlap (e.g. renegotiations);
-- ROW_NUMBER() picks the most recently signed matching contract
-- per player-season to avoid double-counting a claim across
-- multiple contract rows.
--
-- NOTE: not every claim has a matched contract (~35-40% of RB
-- claims, for example) -- likely players on rookie-scale deals
-- or contracts not present in the OTC-sourced contracts table.
-- Unmatched claims are still counted in `n` but excluded from the
-- dollar average, so match rate (matched_n / n) should be read
-- alongside the average, not ignored.
-- =============================================================

WITH all_claims AS (
    SELECT position_group, player_id, season, claim_classification
    FROM player_season_claims_skill
    WHERE claim_classification IN ('PTD', 'TTD')
    UNION ALL
    SELECT position_group, player_id, season, claim_classification
    FROM player_season_claims_ol
    WHERE id_join_matched = 1 AND claim_classification IN ('PTD', 'TTD')
),
ranked_contracts AS (
    SELECT
        c.position_group,
        c.player_id,
        c.season,
        c.claim_classification,
        ct.guaranteed,
        ct.years,
        ROW_NUMBER() OVER (
            PARTITION BY c.position_group, c.player_id, c.season
            ORDER BY ct.year_signed DESC
        ) AS rn
    FROM all_claims c
    LEFT JOIN raw_contracts ct
        ON ct.gsis_id = c.player_id
        AND c.season >= ct.year_signed
        AND c.season < ct.year_signed + ct.years
)
SELECT
    position_group,
    claim_classification,
    COUNT(*)                                              AS n_claims,
    SUM(CASE WHEN guaranteed IS NOT NULL THEN 1 ELSE 0 END) AS matched_n,
    ROUND(
        1.0 * SUM(CASE WHEN guaranteed IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 3
    )                                                       AS contract_match_rate,
    ROUND(AVG(guaranteed * 1.0 / years), 3)                AS avg_annual_guaranteed_at_risk_millions
FROM ranked_contracts
WHERE rn = 1
GROUP BY position_group, claim_classification
ORDER BY
    position_group,
    CASE claim_classification WHEN 'TTD' THEN 1 WHEN 'PTD' THEN 2 END;
