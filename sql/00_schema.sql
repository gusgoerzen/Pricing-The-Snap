-- =============================================================
-- 00_schema.sql
-- Clean, modeled schema (dim/fact tables) built on top of the raw
-- ingestion tables (raw_injuries, raw_rosters, etc.). This is the
-- layer meant to be queried directly for analysis -- the raw_*
-- tables are the ingestion/staging layer, not the analysis layer.
--
-- Populated by scripts/06_build_clean_schema.py, which reads from
-- the raw_* and player_season_claims_* tables built earlier in the
-- pipeline (see scripts/01-03).
--
-- Design notes:
--   - dim_players: one row per player, the dimension table
--   - fact_player_seasons: one row per player-season = exposure base
--   - fact_claims: one row per PTD/TTD/sub-threshold/pending event
--     (excludes non-events -- "excluded_no_claim" isn't a claim)
--   - fact_contracts: one row per signed contract
--   - Foreign keys declared for documentation/integrity even though
--     SQLite doesn't enforce them by default (PRAGMA foreign_keys
--     must be turned on per-connection to enforce).
-- =============================================================

DROP TABLE IF EXISTS fact_claims;
DROP TABLE IF EXISTS fact_player_seasons;
DROP TABLE IF EXISTS fact_contracts;
DROP TABLE IF EXISTS dim_players;

CREATE TABLE dim_players (
    player_id     TEXT PRIMARY KEY,
    player_name   TEXT NOT NULL,
    position_group TEXT NOT NULL CHECK (position_group IN ('RB','OL','QB')),
    birth_date    TEXT
);

CREATE TABLE fact_player_seasons (
    player_id       TEXT NOT NULL,
    season          INTEGER NOT NULL,
    position_group  TEXT NOT NULL,
    age_band        TEXT,
    games_played    INTEGER,
    expected_games  INTEGER,
    is_exposed      INTEGER NOT NULL DEFAULT 1,  -- 1 = counted in exposure base
    PRIMARY KEY (player_id, season),
    FOREIGN KEY (player_id) REFERENCES dim_players(player_id)
);

CREATE TABLE fact_claims (
    claim_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id            TEXT NOT NULL,
    season               INTEGER NOT NULL,
    position_group       TEXT NOT NULL,
    claim_classification TEXT NOT NULL CHECK (
        claim_classification IN ('PTD','TTD','excluded_sub_threshold','pending_immature')
    ),
    games_missed         INTEGER,
    FOREIGN KEY (player_id) REFERENCES dim_players(player_id),
    FOREIGN KEY (player_id, season) REFERENCES fact_player_seasons(player_id, season)
);

CREATE TABLE fact_contracts (
    contract_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT,
    position_group  TEXT NOT NULL,
    year_signed     INTEGER,
    years           INTEGER,
    guaranteed      REAL,
    apy             REAL,
    FOREIGN KEY (player_id) REFERENCES dim_players(player_id)
);

CREATE INDEX idx_fact_player_seasons_season ON fact_player_seasons(season);
CREATE INDEX idx_fact_claims_classification ON fact_claims(claim_classification);
CREATE INDEX idx_fact_claims_player_season ON fact_claims(player_id, season);
CREATE INDEX idx_fact_contracts_player ON fact_contracts(player_id);
