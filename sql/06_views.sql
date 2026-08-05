-- =============================================================
-- 06_views.sql
-- Reusable database views built on top of the clean dim/fact schema
-- (sql/00_schema.sql), rather than every analysis query repeating the
-- same joins/logic from scratch.
-- =============================================================

DROP VIEW IF EXISTS v_claims_with_player;
DROP VIEW IF EXISTS v_exposure_by_position_age;

-- v_claims_with_player: every claim joined to its player + season
-- context (age band, games played that season) -- the base view most
-- claim-level analysis would start from.
CREATE VIEW v_claims_with_player AS
SELECT
    c.claim_id,
    c.player_id,
    p.player_name,
    c.position_group,
    c.season,
    ps.age_band,
    c.claim_classification,
    c.games_missed,
    ps.games_played,
    ps.expected_games
FROM fact_claims c
JOIN dim_players p ON p.player_id = c.player_id
LEFT JOIN fact_player_seasons ps
    ON ps.player_id = c.player_id AND ps.season = c.season;

-- v_exposure_by_position_age: exposure (player-seasons) and claim
-- counts by position + age band, the aggregate a rating table would
-- start from. Reproduces the same result as sql/02, but as a
-- queryable view instead of a one-off script.
CREATE VIEW v_exposure_by_position_age AS
SELECT
    ps.position_group,
    ps.age_band,
    COUNT(*) AS exposure,
    SUM(CASE WHEN c.claim_classification = 'PTD' THEN 1 ELSE 0 END) AS ptd_claims,
    SUM(CASE WHEN c.claim_classification = 'TTD' THEN 1 ELSE 0 END) AS ttd_claims
FROM fact_player_seasons ps
LEFT JOIN fact_claims c
    ON c.player_id = ps.player_id AND c.season = ps.season
GROUP BY ps.position_group, ps.age_band;

-- Example usage (not executed here, just documented):
--   SELECT * FROM v_claims_with_player WHERE claim_classification = 'PTD';
--   SELECT *, ROUND(1.0*ptd_claims/exposure,4) AS ptd_freq
--   FROM v_exposure_by_position_age ORDER BY position_group, age_band;
