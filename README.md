# Pricing the Snap: An Actuarial Approach to NFL Injury Risk

## Project Story

I have an athletic background and a growing interest in actuarial work, and this
project is where those two things meet. Rather than building another NFL stats
dashboard, I wanted to demonstrate the core skills of an actuarial analyst --
frequency/severity modeling, risk classification, exposure/loss analysis, and
product pricing -- applied to a dataset I actually care about.

The core idea: **use real NFL data to design and price a hypothetical
disability insurance product for professional football players**, similar to
real Permanent Total Disability (PTD) and Temporary Total Disability (TTD)
coverages that already exist in professional sports. The NFL is a particularly
interesting setting for this because, unlike the NBA, MLB, and NHL, NFL player
contracts are not fully guaranteed by default -- which makes injury risk a
direct and material financial risk to both the player and the team, not just
a subject for insurance actuaries.

## What This Project Demonstrates

- **Risk classification & rating factors** (Excel) -- segmenting injury risk
  by position, age, and usage, the way an actual rate manual would
- **SQL** -- a structured database of players, contracts, injuries, and
  performance, queried the way a claims/policy database would be
- **Python** -- data ingestion, frequency/severity modeling, survival
  analysis, and a Monte Carlo pricing simulation
- **Dashboards** -- loss experience and rate-table visualization
- **Actuarial product design** -- a short pricing memo for a hypothetical
  PTD/TTD product, complete with stated assumptions and limitations

## Scope

- **Positions:** Running Back (RB), Offensive Line (OL), Quarterback (QB) --
  chosen to span the frequency/severity spectrum (RB: high frequency + high
  severity; OL: high frequency + low severity; QB: lower frequency + highest
  dollar exposure)
- **Products:** Permanent Total Disability (PTD) and Temporary Total
  Disability (TTD), modeled after real disability insurance products used in
  professional sports
- **Seasons:** 2009-2024 (16 seasons) -- bounded by the earliest year official
  weekly injury-report data is available in the source system
- **Data source:** [nflverse](https://github.com/nflverse) via the
  `nfl_data_py` Python package -- injuries, contracts, rosters, snap counts,
  seasonal performance stats, and combine data

See `LIMITATIONS.md` for known data-quality issues and modeling assumptions
found and documented along the way.

## Repository Structure

```
├── scripts/          # Python ingestion & data-processing pipeline
├── sql/              # SQL: schema DDL, views, analysis queries, sample outputs
│   └── sample_output/ # CSV exports of each query's results, for browsing on GitHub
├── excel/             # Rating factor workbook (pivot-style summary, rate lookup tool)
├── notebooks/        # Modeling: frequency/severity, survival analysis, pricing simulation
├── dashboard/         # Power BI / Tableau loss-experience dashboard
├── writeup/           # Product spec + pricing memo
├── data/              # SQLite database (generated locally -- see below, not committed)
├── LIMITATIONS.md      # Data-quality issues & methodology caveats found during the build
└── README.md
```

### SQL layer, in more detail

The `sql/` folder is organized in three layers, in the order a database would actually be built and used:

| File | Purpose |
|---|---|
| `00_schema.sql` | DDL for the clean modeled layer (`dim_players`, `fact_player_seasons`, `fact_claims`, `fact_contracts`) -- built on top of the raw ingestion tables, with primary keys, foreign keys, and indexes |
| `06_views.sql` | Reusable views (`v_claims_with_player`, `v_exposure_by_position_age`) built on the schema above |
| `01`-`05`, `07` | Analysis queries: frequency by position and age band, severity, dollar exposure, rating relativities, and a loss development triangle (claim inception vs. resolution by cohort year, in the style of a P&C reserving triangle) |
| `sample_output/*.csv` | Real output from each query, so results are visible without cloning and running the pipeline |

The schema and views are built by `scripts/06_build_clean_schema.py` (not by `04_run_sql_queries.py`, which only runs the read-only analysis queries).

## Reproducing the Database Locally

The SQLite database (`data/nfl_injury_project.db`) is not committed to this
repo (see `.gitignore`) -- it's fully reproducible by running the scripts in
order:

```bash
pip install -r requirements.txt
cd scripts
python 01_ingest_data.py         # pulls raw data from nflverse -> raw_* tables
python 02_classify_injuries.py   # classifies player-seasons into PTD/TTD/excluded
python 03_exposure.py            # builds exposure base + frequency rates
python 06_build_clean_schema.py  # builds the clean dim/fact schema + views (sql/00, sql/06)
python 04_run_sql_queries.py     # runs every analysis query in sql/ and prints results
python 07_export_sample_outputs.py  # re-exports sql/sample_output/*.csv
```

## Methodology Notes (short version -- see `writeup/` for the full pricing memo)

- **Exposure unit:** player-season (analogous to "car-year" in auto insurance)
- **Claim definition:** a player-season is classified as **TTD** if the player
  missed 6+ games due to injury and returned to play 8+ games within the next
  2 seasons, or **PTD** if no such return was observed. Seasons with fewer
  than 6 games missed, or no injury designation, are excluded as non-claims.
- **Credibility:** this project does not reach classical full-credibility
  claim volumes (~1,082 claims). It operates at partial credibility, which is
  disclosed explicitly rather than presented as more certain than it is --
  consistent with how real actuarial work handles thin segments.

## Disclaimer

This is a personal portfolio/learning project. It does not represent an
actual insurance product, is not affiliated with the NFL, NFLPA, or any
insurer, and should not be used as a basis for real underwriting or pricing
decisions.
