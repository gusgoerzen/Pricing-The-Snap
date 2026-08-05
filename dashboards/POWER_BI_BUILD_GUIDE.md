# Power BI Dashboard Build Guide

This is a step-by-step guide to building the Phase 6 dashboard in Power BI
Desktop, using the CSVs in `dashboard/data/`. Follow this whenever you're
ready to actually build it -- it's written to be self-contained so you
don't need to re-derive the plan from scratch later.

**Prerequisite:** Power BI Desktop installed (free, from Microsoft --
not the Teams/work version). See the note in this project's chat history
if you need the download link again.

---

## Step 1: Import the data

1. Open Power BI Desktop
2. **Home > Get Data > Text/CSV**
3. Import all 6 files from `dashboard/data/`, one at a time:
   - `player_season_data.csv`
   - `exposure_frequency.csv`
   - `rating_relativities.csv`
   - `loss_development_triangle.csv`
   - `contract_severity.csv`
   - `pricing_scenarios.csv`
4. For each, click **Load** (not "Transform Data" -- these are already
   clean, no transformation needed)

## Step 2: Set up relationships (Model view)

Click the **Model** icon on the left sidebar (looks like a small diagram).
`player_season_data` is your main fact table -- drag to connect:

- `player_season_data[position_group]` -> `exposure_frequency[position_group]`
- `player_season_data[position_group]` -> `rating_relativities[position_group]`
- `player_season_data[position_group]` -> `contract_severity[position_group]`

Leave `loss_development_triangle` and `pricing_scenarios` **unconnected** --
they're standalone summary tables, not meant to cross-filter with the
player-level data (their grain is different: cohort-year and
scenario-based, not player-season-based).

---

## Step 3: Build the pages

Create 4 report pages (right-click the page tabs at the bottom > rename).

### Page 1: Loss Experience Overview

**Purpose:** the "what does the risk look like" page -- mirrors the SQL/Excel
rating table work.

- **Visual 1 (top-left): Matrix**
  - Rows: `exposure_frequency[position_group]`, then `exposure_frequency[age_band]`
  - Values: `exposure`, `ptd_claims`, `ttd_claims`, `ptd_frequency`, `ttd_frequency`
  - Format `ptd_frequency`/`ttd_frequency` as percentage (right-click the
    field > Format > Percentage)

- **Visual 2 (top-right): Clustered column chart**
  - Axis: `age_band`
  - Legend: `position_group`
  - Values: `ptd_frequency`
  - Title: "PTD Frequency by Position and Age"

- **Visual 3 (bottom): Card visuals (x2)**
  - Card 1: Sum of `exposure_frequency[exposure]` -> label "Total Player-Seasons"
  - Card 2: Sum of `ptd_claims` + Sum of `ttd_claims` -> label "Total Claims"
    (use a measure: `Total Claims = SUM(exposure_frequency[ptd_claims]) + SUM(exposure_frequency[ttd_claims])`)

- **Slicer:** add a slicer visual for `position_group` at the top of the
  page so all visuals filter together

### Page 2: Rating & Severity

**Purpose:** the rate-manual page -- relativities and dollar severity.

- **Visual 1 (left): Clustered bar chart**
  - Axis: `rating_relativities[position_group]`
  - Values: `ptd_relativity`, `ttd_relativity`
  - Title: "Rating Relativities (Base = OL/TTD)"
  - Add a reference line at y=1.0 (Format pane > Add a constant line) to
    visually mark the base class

- **Visual 2 (right): Box-and-whisker chart** (may require the "Box and
  Whisker Chart" visual from the Power BI marketplace -- AppSource -- if
  not built in; free and safe to add)
  - Category: `contract_severity[position_group]`
  - Value: `annual_guaranteed_at_risk_millions`
  - Split by `claim_classification` if the visual supports a legend
  - Title: "Dollar Severity Distribution by Position"

If you don't want to install the marketplace visual, a clustered column
chart of **average** `annual_guaranteed_at_risk_millions` by
`position_group` and `claim_classification` is a fine simpler substitute.

### Page 3: Loss Development

**Purpose:** the reserving-triangle page -- shows how claims resolve over
time, the same insight as `sql/07_loss_development_triangle.sql`.

- **Visual 1 (full width): Line chart**
  - Axis: `injury_season`
  - Values: `dev_0_claims_incepted`, `dev_1_cumulative_resolved`, `dev_2_cumulative_resolved`
  - Title: "Claims Incepted vs. Resolved, by Injury Cohort Year"

- **Visual 2 (below): Line chart**
  - Axis: `injury_season`
  - Values: `pct_of_final_ttd_resolved_by_dev1`
  - Format as percentage
  - Title: "% of Eventual TTD Cases Resolved Within 1 Season"

### Page 4: Pricing Simulation

**Purpose:** the payoff page -- the flat-vs-percentage attachment finding
from the pricing memo.

- **Visual 1 (left): Clustered column chart**
  - Axis: `position` + `age` (you may want to combine these into one text
    field for a cleaner axis label -- see note below)
  - Values: `flat_mean_premium_M`, `pct_structure_mean_premium_M`
  - Title: "Pure Premium: Flat vs. Percentage-of-Contract Structure"

- **Visual 2 (right): Clustered column chart**
  - Same axis
  - Values: `flat_pct_zero_payout`, `pct_structure_pct_zero_payout`
  - Format as percentage
  - Title: "% of Claims With Zero Payout, By Structure"

**Note:** to get a clean combined axis label like "RB-23", add a calculated
column in Power Query or DAX:
`Scenario = pricing_scenarios[position] & "-" & pricing_scenarios[age]`

---

## Step 4: Polish

- Add a title text box at the top of each page
- Pick one consistent color for "flat structure" visuals and a different
  one for "percentage structure" visuals across Page 4, so the comparison
  reads clearly even without checking the legend every time
- Add a text box on Page 1 with a one-line project summary (pulled from
  the README) so the dashboard is self-explanatory if viewed on its own

## Step 5: Save and add to the repo

1. **File > Save As** -> save as `dashboard/nfl_injury_dashboard.pbix`
2. Add the `.pbix` file to your repo the same way as the Excel workbook
   (drag-and-drop upload into the `dashboard/` folder on GitHub)
3. GitHub can't render `.pbix` files inline (same limitation as `.xlsx`),
   so also take a couple of screenshots of your finished pages and add
   them to `dashboard/screenshots/` -- this lets someone browsing the repo
   see the dashboard without needing Power BI installed, similar to how
   `sql/sample_output/*.csv` lets people see SQL results without running
   the pipeline

## Optional: publish for a shareable link

If you want a live, clickable dashboard link (not just a downloadable
file) for recruiters: **Home > Publish** in Power BI Desktop, using a free
personal Power BI account (not your SPG work account -- see the earlier
discussion on why to keep this project separate from your employer's
tenant). This gives you a URL you can link directly from your README.
