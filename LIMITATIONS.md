# Limitations & Methodology Notes

This is a running log of real data-quality issues, source constraints, and
methodology decisions found while building this project. Kept honest and
updated as the project progresses -- an actuarial pricing exercise is only as
credible as its disclosed assumptions and limitations.

## Data source constraints

- **Injury report data starts in 2009**, not 2005. The project's original
  20-year window (2005/06-2025/26) was narrowed to 2009-2024 (16 seasons) for
  this reason. Roster, contract, and performance data are technically
  available further back, but were scoped to match the injury data window for
  consistency.
- **Snap count data starts in 2012.** Used as the primary "games played" proxy
  for offensive linemen (who have no comparable box-score stat). 2009-2011 OL
  seasons cannot be classified via this method.
- **PFR advanced stats (broken tackles, yards after contact, etc.) start in
  2018.** Used only as a supplementary enrichment table for RB/QB, not as the
  primary performance metric. The primary performance metric across the full
  2009-2024 window is EPA (Expected Points Added) from `nfl_data_py`'s core
  seasonal stats table.
- **2025-2026 season excluded entirely** -- season in progress at time of
  build, would distort injury classification (18-month return window can't be
  observed yet).
- **2023-2024 seasons flagged as "pending_immature"** in the classification
  step, not force-classified as PTD/TTD, since there hasn't been enough time
  to observe a return-or-not outcome. Same logic as an "immature accident
  year" in loss reserving.

## Join / ID mapping issues

- **Offensive linemen have 0% `pfr_id` coverage** in the nflverse rosters
  table (confirmed by direct inspection, not assumed). This breaks the
  intended primary join path (`pfr_id`) between snap counts and PFR-based
  tables for this position group.
- **Workaround:** OL records are bridged to `gsis_id` (used by the injuries
  table) via a name + season match against the rosters table, verified at
  ~97.6% match rate during development. The ~2.4% that don't match are
  tagged `unclassified_no_id_match` and excluded from claim classification
  rather than silently dropped or guessed at.
- **Position labels differ across source tables** (e.g., contracts uses
  granular `RT/LG/LT/RG/C`, rosters/snap counts use a mix of consolidated
  `OL` and split `T/G/C`). A single position-mapping dictionary is applied at
  ingestion (see `POSITION_MAP` in `01_ingest_data.py`) to normalize all
  sources to `RB` / `OL` / `QB` consistently.

## Modeling / classification assumptions

- **Season-level, not game-level, classification.** Injury episodes are
  classified based on games missed *within a season* relative to that
  season's expected game count (16 games through 2020, 17 from 2021 on), not
  exact injury start/end dates. This matches the player-season exposure base
  but is a real simplification -- a mid-season injury that costs a player the
  back half of one season and the front half of the next is not modeled as a
  single continuous episode.
- **Attribution is not causally proven.** A player-season is only classified
  as a claim if there's *also* a matching injury-report designation
  (Out/Doubtful), but this doesn't prove the injury *caused* a subsequent
  non-return -- age, performance decline, and roster decisions are entangled
  with injury in real career endings. This was spot-checked on a small sample
  of QB "PTD" cases (e.g., journeyman veterans whose careers ended following
  a flagged injury season) and looked directionally reasonable, but this is
  an assumption, not a proven causal claim.
- **"Sub-threshold" tier (2-5 games missed) tracked but not used as a claim.**
  The original 3-tier rule (excluded / TTD / PTD) had a gap for 2-5 games
  missed. Rather than silently lumping this into "excluded," these rows are
  tagged `excluded_sub_threshold` so the option exists to build a third
  product tier later if useful.
- **Return threshold:** a player is only considered to have "returned" from a
  TTD-qualifying injury if they played 8+ games in one of the next 2 seasons
  -- a token 1-2 game appearance does not count as a real recovery.

## Exposure base sensitivity

Two exposure denominators are calculated and reported side by side, not
collapsed into one number:

- **Broad exposure:** every rostered player-season, excluding practice-squad
  -only (`DEV` status) rows.
- **Refined exposure:** broad exposure minus player-seasons where the player
  had 0 games played AND was not classified as any kind of injury claim
  (i.e., likely a training-camp cut who was never really "at risk" in the
  sense this project measures).

Frequency rates differ meaningfully between the two (refined rates run
higher across every position/product combination), which is disclosed rather
than picking one and hiding the sensitivity. See `exposure_frequency` table.

## Known result that deserves a real explanation, not just a footnote

Actual PTD frequency came in **higher** than originally assumed, and actual
TTD frequency came in **lower**, across all three positions (see project
notes / pricing memo for the full comparison table). Working hypothesis:
once a player clears the "missed 6+ games" bar, non-return within 2 seasons
is more common than partial-return-and-continue, which pushes more cases
into PTD than a naive injury-severity intuition would suggest. This is
flagged as a finding worth investigating further (e.g., breaking out by age
at time of injury) rather than an error to silently correct.

## Credibility

This project does not reach classical full-credibility standards (~1,082
claims for a 90%/±5% standard). All 6 position/product cells exceed a
practical minimum-events-per-variable heuristic (~40-50 claims for a model
with 4-5 rating factors), with QB/TTD (36 claims) coming in slightly under
that bar. This is disclosed as a partial-credibility result, consistent with
how real actuarial work treats thin segments -- not glossed over as if the
volume were fully sufficient.

## Pricing memo: flat vs. percentage-of-contract attachment structure

A flat dollar attachment point ($0.5M), tested in
`notebooks/03_pricing_simulation.ipynb`, was found to produce zero payout
on 71.9% of real RB claims and 55.3% of real OL claims, because the
attachment was implicitly sized for QB-scale contracts. A percentage-of-
contract structure (attachment/limit as a % of the player's own contract
value, rather than a flat number) fixes this -- but because severity in
this model *is* the player's annualized guaranteed money itself (not an
independently observed fraction of it), a percentage-based attachment
mechanically produces a payout on nearly every claim by construction
(except true $0-guaranteed contracts). The fix is structurally correct for
the scaling problem it addresses, but the specific 20%/100% split used was
chosen for illustration, not calibrated to a target loss ratio -- a real
pricing exercise would tune that split against actual target economics,
not assume a round number.
