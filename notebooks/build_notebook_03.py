"""
Builds notebooks/03_pricing_simulation.ipynb -- a Monte Carlo simulation
of a hypothetical PTD/TTD insurance product, using the fitted GLMs from
notebook 1 (frequency) and empirical contract data (severity).

Run: python build_notebook_03.py
Requires: fitted_models.pkl (produced by notebook 1)
"""
import nbformat as nbf
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell
from nbclient import NotebookClient

cells = []

cells.append(new_markdown_cell(
"""# Pricing Simulation: A Hypothetical PTD/TTD Product

**Goal:** simulate a "book" of insured players under a hypothetical
disability insurance structure (attachment point + limit, like the real
TTD policies described in the Sportico/Rodgers reporting), and estimate
the distribution of aggregate losses -- the core Monte Carlo exercise real
pricing actuaries run before setting a premium.

**Inputs:**
- **Frequency**: the PTD and TTD logistic GLMs fitted in notebook 1
  (probability of each outcome, by position + age)
- **Severity**: empirical annual guaranteed-money-at-risk, bootstrap-
  sampled from real contract data matched to real claims (same logic as
  `sql/04_dollar_exposure_by_classification.sql`)

**Policy structure simulated:** attachment point (like a deductible) and a
limit (max payout per claim) -- the same structure real TTD/PTD policies
use."""
))

cells.append(new_code_cell(
"""%matplotlib inline
import sqlite3
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

np.random.seed(42)

DB_PATH = "../data/nfl_injury_project.db"
conn = sqlite3.connect(DB_PATH)

with open("fitted_models.pkl", "rb") as f:
    models = pickle.load(f)
model_ptd = models["ptd"]
model_ttd = models["ttd"]
print("Loaded fitted frequency models from notebook 1.")"""
))

cells.append(new_markdown_cell(
"""## 1. Pull the empirical severity distribution (dollar terms)

Same contract-matching logic as `sql/04` -- for each real claim, find the
guaranteed money at risk that season, expressed as an annualized figure
($M/year of the contract)."""
))

cells.append(new_code_cell(
"""severity_query = '''
WITH ranked_contracts AS (
    SELECT
        c.position_group, c.player_id, c.season, c.claim_classification,
        ct.guaranteed, ct.years,
        ROW_NUMBER() OVER (
            PARTITION BY c.position_group, c.player_id, c.season
            ORDER BY ct.year_signed DESC
        ) AS rn
    FROM fact_claims c
    LEFT JOIN fact_contracts ct
        ON ct.player_id = c.player_id
        AND c.season >= ct.year_signed
        AND c.season < ct.year_signed + ct.years
    WHERE c.claim_classification IN ('PTD','TTD')
)
SELECT position_group, claim_classification, guaranteed*1.0/years AS annual_guaranteed_at_risk
FROM ranked_contracts
WHERE rn = 1 AND guaranteed IS NOT NULL
'''
severity = pd.read_sql(severity_query, conn)
severity.groupby(["position_group","claim_classification"])["annual_guaranteed_at_risk"].describe().round(2)"""
))

cells.append(new_markdown_cell(
"""## 2. The simulation function

For a given position and age:
1. Predict P(PTD) and P(TTD) from the fitted frequency GLMs
2. Simulate a book of `n_players` for `n_sims` iterations
3. For each simulated player, draw a claim outcome from the predicted
   probabilities; if a claim occurs, bootstrap-sample a dollar severity
   from the real empirical distribution for that position/classification
4. Apply the policy structure (attachment point, limit) to get the payout
5. Sum payouts across the book to get one simulated "aggregate annual
   loss" draw; repeat `n_sims` times to build a full distribution"""
))

cells.append(new_code_cell(
"""def simulate_book(position, age, n_players=50, n_sims=10000, attachment=0.5, limit=5.0):
    X = pd.DataFrame({"position_group": [position], "age": [age]})
    p_ptd = model_ptd.predict(X).iloc[0]
    p_ttd = model_ttd.predict(X).iloc[0]
    p_none = 1 - p_ptd - p_ttd
    probs = [p_none, p_ptd, p_ttd]

    ptd_pool = severity[
        (severity.position_group == position) & (severity.claim_classification == "PTD")
    ]["annual_guaranteed_at_risk"].values
    ttd_pool = severity[
        (severity.position_group == position) & (severity.claim_classification == "TTD")
    ]["annual_guaranteed_at_risk"].values

    totals = np.zeros(n_sims)
    for i in range(n_sims):
        outcomes = np.random.choice(["none", "PTD", "TTD"], size=n_players, p=probs)
        book_loss = 0.0
        for o in outcomes:
            if o == "PTD":
                loss = np.random.choice(ptd_pool)
            elif o == "TTD":
                loss = np.random.choice(ttd_pool)
            else:
                continue
            payout = min(max(loss - attachment, 0), limit)
            book_loss += payout
        totals[i] = book_loss
    return probs, totals

print("Simulation function defined.")"""
))

cells.append(new_markdown_cell(
"""## 3. Run the simulation: a 50-player RB book, age 25

Policy structure: $0.5M attachment point, $5M limit per claim (illustrative
-- in the same order of magnitude as the real Rodgers TTD policy premiums
reported by Sportico, which ran $1-4M for ~60% coverage of a $37M salary)."""
))

cells.append(new_code_cell(
"""probs, totals = simulate_book("RB", age=25, n_players=50, n_sims=10000, attachment=0.5, limit=5.0)

print(f"P(no claim) = {probs[0]:.3f}, P(PTD) = {probs[1]:.3f}, P(TTD) = {probs[2]:.3f}")
print()
print(f"Mean aggregate annual loss (book of 50 RBs): ${totals.mean():.2f}M")
print(f"Std dev: ${totals.std():.2f}M")
print(f"P50 (median): ${np.percentile(totals, 50):.2f}M")
print(f"P95: ${np.percentile(totals, 95):.2f}M")
print(f"P99: ${np.percentile(totals, 99):.2f}M")"""
))

cells.append(new_code_cell(
"""fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(totals, bins=50, color="#2563eb", alpha=0.8)
ax.axvline(totals.mean(), color="black", linestyle="--", label=f"Mean = ${totals.mean():.2f}M")
ax.axvline(np.percentile(totals, 95), color="red", linestyle="--", label=f"P95 = ${np.percentile(totals,95):.2f}M")
ax.set_xlabel("Aggregate annual loss, book of 50 RBs ($M)")
ax.set_ylabel("Simulation count")
ax.set_title("Monte Carlo: Aggregate Annual Loss Distribution (RB, age 25)")
ax.legend()
plt.tight_layout()
plt.savefig("pricing_sim_rb25.png", dpi=120)
plt.show()"""
))

cells.append(new_markdown_cell(
"""## 4. Compare across positions and ages

Running the same simulation for a few different position/age combinations
shows how the *pure premium per player* (mean aggregate loss / number of
players) scales -- the actual number a pricing memo would quote."""
))

cells.append(new_code_cell(
"""scenarios = [
    ("RB", 23), ("RB", 27), ("RB", 31),
    ("OL", 27), ("QB", 27),
]

rows = []
for pos, age in scenarios:
    probs, totals = simulate_book(pos, age, n_players=50, n_sims=5000, attachment=0.5, limit=5.0)
    rows.append({
        "position": pos, "age": age,
        "p_ptd": probs[1], "p_ttd": probs[2],
        "mean_pure_premium_per_player_M": totals.mean() / 50,
        "p95_pure_premium_per_player_M": np.percentile(totals, 95) / 50,
    })

pd.DataFrame(rows).round(4)"""
))

cells.append(new_markdown_cell(
"""**Reading this table:** pure premium per player rises sharply with RB age
(23 -> 31), consistent with the frequency model's age effect on PTD.
Comparing RB/OL/QB at the same age (27) shows RB carrying the highest
expected cost per player, with QB elevated too, reflecting the much
higher dollar severity found in the contracts data even though QB claim
*frequency* is lower than RB's -- frequency and severity pull in different
directions here, exactly the kind of tension a real pricing exercise has
to reconcile, not just average away.

## 5. Note on loading (this is pure premium, not a quoted price)

Everything above is **pure premium** -- the expected claims cost with no
margin. A real quoted premium would add loadings for expenses, profit,
and risk margin (e.g., loading for the P95/P99 tail risk shown above,
not just the mean). This notebook stops at pure premium deliberately --
the loading assumptions belong in the pricing memo (`writeup/`), as a
business/underwriting judgment call, not a statistical one."""
))

cells.append(new_code_cell(
"""conn.close()"""
))

nb = new_notebook(cells=cells)
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}

client = NotebookClient(nb, timeout=180, kernel_name="python3", resources={"metadata": {"path": "."}})
client.execute()

with open("03_pricing_simulation.ipynb", "w") as f:
    nbf.write(nb, f)

print("Notebook executed and saved successfully.")
