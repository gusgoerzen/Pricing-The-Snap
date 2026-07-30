-- =============================================================
-- 01_frequency_by_position.sql
-- Business question: "What's our loss frequency by position and
-- product, and how much exposure is it based on?"
--
-- This is the same output produced by scripts/03_exposure.py, but
-- built here as a standalone SQL view directly against the
-- exposure_frequency table -- demonstrating the query layer a real
-- analyst would run, not just a one-off Python script.
-- =============================================================

SELECT
    position_group,
    SUM(broad_exposure)                                  AS total_broad_exposure,
    SUM(refined_exposure)                                AS total_refined_exposure,
    SUM("PTD")                                            AS total_ptd_claims,
    SUM("TTD")                                            AS total_ttd_claims,
    ROUND(1.0 * SUM("PTD") / SUM(broad_exposure), 4)      AS ptd_frequency_broad,
    ROUND(1.0 * SUM("TTD") / SUM(broad_exposure), 4)      AS ttd_frequency_broad,
    ROUND(1.0 * SUM("PTD") / SUM(refined_exposure), 4)    AS ptd_frequency_refined,
    ROUND(1.0 * SUM("TTD") / SUM(refined_exposure), 4)    AS ttd_frequency_refined
FROM exposure_frequency
GROUP BY position_group
ORDER BY position_group;
