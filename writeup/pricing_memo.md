# Pricing Memo: Hypothetical NFL Disability Insurance Product

**Prepared as part of the Pricing the Snap portfolio project. Not an actual
insurance filing, and not affiliated with the NFL, NFLPA, or any insurer.
See `LIMITATIONS.md` for the full methodology caveats referenced throughout.**

---

## 1. Product Overview

This memo prices two hypothetical disability insurance products modeled on
real coverages used in professional football:

| Product | What it covers | Real-world analogue |
|---|---|---|
| **TTD** (Temporary Total Disability) | A season-hampering injury from which the player returns to meaningful play (8+ games) within roughly 18 months | The TTD policies NFL teams can buy today, which recoup a portion of guaranteed salary if a player suffers a season-hampering injury (Source: Sportico) |
| **PTD** (Permanent Total Disability) | An injury from which the player does not return to meaningful NFL play within that window | Career-ending injury coverage used across pro sports |

**Target insured:** the team, not the player -- consistent with how real TTD
coverage is written today. Unlike the NBA and NHL, which require teams to
insure their highest-paid players through league-wide programs, the NFL
leaves this decision entirely up to individual teams, which is exactly the
gap this product is designed to fill.

**Real-world stakes:** a 2023 Sportico investigation reported that the
New York Jets were offered, and declined, multiple TTD policies on Aaron
Rodgers before the 2023 season -- a decision estimated to have cost the
team over $20 million in insurance proceeds once he suffered a
season-ending Achilles injury in the opener. Reported premiums for those
policies ranged from roughly $1 million to $4 million, with the higher end
covering about 60% of his $37 million guaranteed salary that year. That
real premium range is a useful outside check on the indicated figures
below. (Source: Sportico, October 2023.)

**Policy structure priced here:** an attachment point (like a deductible) of
$0.5M and a limit of $5M per claim, applied to the player's annualized
guaranteed money at risk. Both are illustrative choices for this exercise,
not a specific recommendation.

---

## 2. Underwriting Classes

Three position groups, chosen to span the frequency/severity spectrum, and
four age bands. Position and age are used as rating variables based on
statistically significant results from the fitted frequency GLMs
(`notebooks/01_frequency_severity_modeling.ipynb`):

- **RB**: highest PTD frequency of the three positions, and PTD odds
  increase significantly with age (p < 0.001)
- **OL**: used as the base class -- highest-volume, most stable segment
- **QB**: lowest claim frequency, but by far the highest dollar severity per
  claim, due to guaranteed-money concentration at the position

### Rating relativities (relative to OL/TTD base), from `sql/05_rating_relativities.sql`

| Position | PTD Frequency | TTD Frequency | PTD Relativity | TTD Relativity |
|---|---|---|---|---|
| OL | 3.36% | 3.00% | 1.12 | 1.00 (base) |
| QB | 5.05% | 2.16% | 1.68 | 0.72 |
| RB | 6.49% | 4.87% | 2.16 | 1.62 |

---

## 3. Indicated Pure Premium

The figures below come from the Monte Carlo simulation in
`notebooks/03_pricing_simulation.ipynb`, which combines the fitted frequency
GLMs with empirical, contract-derived severity data (10,000 simulated
seasons per scenario). Figures are **pure premium per player** -- expected
claims cost only, with no expense, profit, or risk margin loading.

| Position | Age | P(PTD) | P(TTD) | Mean Pure Premium ($M/player) | P95 Pure Premium ($M/player) |
|---|---|---|---|---|---|
| RB | 23 | 5.45% | 5.59% | 0.045 | 0.139 |
| RB | 25 | 6.38% | 5.27% | 0.045 | 0.140 |
| RB | 27 | 7.45% | 4.96% | 0.044 | 0.139 |
| RB | 31 | 10.12% | 4.40% | 0.046 | 0.138 |
| OL | 27 | 3.48% | 3.27% | 0.061 | 0.193 |
| QB | 27 | 4.42% | 2.29% | 0.152 | 0.362 |

**The QB finding is the most important pricing insight in this memo.**
Despite QB having the *lowest combined claim frequency* of the three
positions, QB carries the *highest* pure premium per player by a wide
margin -- more than 3x the RB or OL figure at the same age. This is a pure
severity effect: guaranteed money at the QB position is concentrated
enough that even a lower-frequency claim is, on average, far more
expensive. **Frequency and severity point in different directions here,
and a rating plan built on frequency alone would badly underprice QB
risk.**

RB pure premium is relatively flat across age in dollar terms, even though
PTD *frequency* rises sharply with age (5.45% -> 10.12%) -- because TTD
frequency falls roughly offsetting amount over the same age range, and
severity doesn't vary much with age (see Section 4). This is a case where
looking at frequency alone would overstate how much age actually matters
to the *priced* risk.

---

## 4. Supporting Evidence From Other Parts of the Project

This memo's numbers aren't produced in isolation -- they're corroborated
across three independent parts of the project:

- **Severity is driven by claim type, not position/age.** The Gamma GLM
  severity model (`notebooks/01`) found position and age were not
  significant predictors of games missed once a claim occurs, but PTD vs.
  TTD classification was highly significant (p < 0.001). This supports
  pricing frequency by segment but treating severity more uniformly within
  a claim type, which is exactly what the Monte Carlo simulation does.
- **The frequency differences are not noise.** The Kaplan-Meier log-rank
  test (`notebooks/02`) confirmed the difference in return-to-play patterns
  across positions is statistically significant (p = 0.004), independent
  of the GLM's own significance tests.
- **Most resolution happens fast, if it happens at all.** The loss
  development triangle (`sql/07_loss_development_triangle.sql`) found that
  86.3% of all claims that eventually resolve as TTD do so within just one
  season -- the "second chance" year adds comparatively little. Combined
  with the finding that more than half of all serious-injury cases (games
  missed >= 6, injury-flagged) never resolve as TTD at all within the
  2-season window, this supports treating a claim's outcome as largely
  determined early, rather than assuming a long, gradual recovery curve.

---

## 5. Worked Example

A 25-year-old RB signs a contract with $2M/year in guaranteed money. Under
the policy structure priced here ($0.5M attachment, $5M limit):

- If this player suffers a claim, the modeled *expected* payout, before
  applying the attachment/limit structure to any specific claim, draws
  from the empirical RB severity distribution (mean annual guaranteed at
  risk ~$0.36M for PTD, ~$0.91M for TTD; see `sql/04`) -- both comfortably
  within the $5M limit and mostly below the $0.5M attachment on any single
  claim, meaning **most individual RB claims in this dataset would not
  actually trigger a payout under this specific attachment point.**
- This is a real, honest finding, not a flaw in the pricing: it says the
  $0.5M attachment point, calibrated with a QB-sized contract in mind, is
  too high to be useful for a typical RB contract. **A real product would
  need position-specific attachment points**, not one global structure --
  exactly the kind of segmentation insight a pricing exercise is supposed
  to surface.

---

## 6. Assumptions & Limitations (See `LIMITATIONS.md` for Full Detail)

- Pure premium only -- no expense, profit, or risk margin loading applied.
- Severity is bootstrap-sampled from a modest number of real claims per
  position/classification cell (as few as 33 for QB/TTD); tail estimates
  (P95, P99) are less stable than the mean for the thinnest cells.
- The frequency GLMs use position and age only. A real rating plan would
  likely add usage/workload variables (e.g., snap counts, prior injury
  history), which were explored in the SQL/Excel layers but not yet built
  into the GLM.
- Claim classification is season-level, not exact-date, and attribution
  (does the injury *cause* non-return, or merely coincide with it) is not
  proven causally -- both are disclosed modeling simplifications carried
  through from earlier phases of this project, not new to this memo.
- This product structure (fixed attachment/limit across all positions) is
  shown in Section 5 to be a real limitation of this specific exercise, not
  a general critique of TTD/PTD insurance -- real policies are individually
  underwritten per player and contract.

---

## 7. Disclaimer

This is a personal portfolio/learning project. It does not represent an
actual insurance product, is not a regulatory filing, and should not be
used as a basis for real underwriting, pricing, or coverage decisions.
