-- =============================================================
-- 05_rating_relativities.sql
-- Business question: "If we treat OL/TTD as our base rating
-- class, how much higher or lower is the risk for every other
-- position/product cell?" -- this is the relativity-table format
-- real rate manuals use to communicate risk differences across
-- classes.
--
-- OL/TTD is chosen as the base class because it's the highest-
-- volume, most stable cell in the portfolio (highest exposure,
-- solid claim count) -- a reasonable, defensible base rate choice,
-- not an arbitrary one.
-- =============================================================

WITH freq AS (
    SELECT
        position_group,
        ROUND(1.0 * SUM("PTD") / SUM(broad_exposure), 4) AS ptd_freq,
        ROUND(1.0 * SUM("TTD") / SUM(broad_exposure), 4) AS ttd_freq
    FROM exposure_frequency
    GROUP BY position_group
),
base AS (
    SELECT ttd_freq AS base_rate FROM freq WHERE position_group = 'OL'
)
SELECT
    f.position_group,
    f.ptd_freq,
    f.ttd_freq,
    ROUND(f.ptd_freq / b.base_rate, 2) AS ptd_relativity_to_OL_TTD_base,
    ROUND(f.ttd_freq / b.base_rate, 2) AS ttd_relativity_to_OL_TTD_base
FROM freq f, base b
ORDER BY f.position_group;
