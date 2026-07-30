-- =============================================================
-- 02_frequency_by_age_band.sql
-- Business question: "How does injury frequency vary by player
-- age, within each position group?" -- this is a core rating
-- factor input (age band), not yet covered by the Python pipeline.
--
-- Age is computed at each player's season start (approximated as
-- Sept 1 of that season) from birth_date in raw_rosters. Players
-- with missing birth_date (~5% of rows) are grouped into an
-- "Unknown" band rather than dropped or guessed at.
--
-- NOTE: exposure here is "broad" exposure (all rostered
-- player-seasons excl. practice squad), matching the definition
-- used in scripts/03_exposure.py.
-- =============================================================

WITH roster_age AS (
    SELECT
        r.position_group,
        r.season,
        r.player_id,
        CASE
            WHEN r.birth_date IS NULL THEN NULL
            ELSE CAST((julianday(r.season || '-09-01') - julianday(r.birth_date)) / 365.25 AS INTEGER)
        END AS age_at_season
    FROM raw_rosters r
    WHERE r.status != 'DEV'
),
age_banded AS (
    SELECT
        position_group,
        season,
        player_id,
        CASE
            WHEN age_at_season IS NULL THEN 'Unknown'
            WHEN age_at_season <= 24 THEN '<=24'
            WHEN age_at_season <= 27 THEN '25-27'
            WHEN age_at_season <= 30 THEN '28-30'
            ELSE '31+'
        END AS age_band
    FROM roster_age
),
exposure_by_band AS (
    SELECT position_group, age_band, COUNT(*) AS exposure
    FROM age_banded
    GROUP BY position_group, age_band
),
claims_skill AS (
    SELECT position_group, season, player_id, claim_classification
    FROM player_season_claims_skill
    WHERE claim_classification IN ('PTD', 'TTD')
),
claims_ol AS (
    SELECT position_group, season, player_id, claim_classification
    FROM player_season_claims_ol
    WHERE claim_classification IN ('PTD', 'TTD') AND id_join_matched = 1
),
claims_all AS (
    SELECT * FROM claims_skill
    UNION ALL
    SELECT * FROM claims_ol
),
claims_banded AS (
    SELECT c.position_group, ab.age_band, c.claim_classification, COUNT(*) AS n
    FROM claims_all c
    JOIN age_banded ab
        ON ab.position_group = c.position_group
        AND ab.season = c.season
        AND ab.player_id = c.player_id
    GROUP BY c.position_group, ab.age_band, c.claim_classification
)
SELECT
    e.position_group,
    e.age_band,
    e.exposure,
    COALESCE(SUM(CASE WHEN cb.claim_classification = 'PTD' THEN cb.n END), 0) AS ptd_claims,
    COALESCE(SUM(CASE WHEN cb.claim_classification = 'TTD' THEN cb.n END), 0) AS ttd_claims,
    ROUND(1.0 * COALESCE(SUM(CASE WHEN cb.claim_classification = 'PTD' THEN cb.n END), 0) / e.exposure, 4) AS ptd_frequency,
    ROUND(1.0 * COALESCE(SUM(CASE WHEN cb.claim_classification = 'TTD' THEN cb.n END), 0) / e.exposure, 4) AS ttd_frequency
FROM exposure_by_band e
LEFT JOIN claims_banded cb
    ON cb.position_group = e.position_group AND cb.age_band = e.age_band
GROUP BY e.position_group, e.age_band, e.exposure
ORDER BY
    e.position_group,
    CASE e.age_band
        WHEN '<=24' THEN 1
        WHEN '25-27' THEN 2
        WHEN '28-30' THEN 3
        WHEN '31+' THEN 4
        ELSE 5
    END;
