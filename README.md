# EPL Match Predictor

End-to-end pipeline that scrapes 11 seasons of English Premier League data, engineers 34 match-level features, and predicts outcomes using a tuned LightGBM + Poisson ensemble. All code lives in a single Jupyter notebook: `epl_predictor.ipynb`.

---

## What it does

Given any two EPL teams, the model outputs:
- Win / draw / loss probabilities
- Expected goals (home and away)
- Predicted scoreline
- Pre-match Elo ratings for both sides

---

## Data sources

| Source | Method | What's collected |
|---|---|---|
| **FBref** | ScraperFC + botasaurus (Chrome) | 400+ squad and opponent stats per team per season — shooting, passing, defense, possession, misc |
| **Understat** | Selenium (Chrome, headless-optional) | Match-level xG, season table (xG/xGA/PPDA/xPTS), player stats |
| **SofaScore** | ScraperFC API | Team league stats, player stats by position group |
| **Transfermarkt** | requests + BeautifulSoup (Selenium fallback) | Current season injuries and net transfer balance per club |
| **Football-Data.co.uk** | CSV download | Closing odds (B365 + Pinnacle) for all 11 seasons |

Seasons covered: **2015-16 through 2025-26**

---

## Feature engineering

All raw files are merged into a single `data/ml_dataset.csv` with one row per match and 34 features:

**Season-level stats** (from Understat + FBref, per team)
- xG For/90, xGA/90, xGD/90, xA/90
- PPDA (passes allowed per defensive action — pressing intensity)
- OPPDA (opponent's PPDA — how hard they press you)
- Shot on Target %, Save %

**Rolling form** (last 5 and last 10 matches, shift(1) to prevent leakage)
- Points accumulated, goal difference

**Contextual**
- Days rest since last match (capped at 30 days to ignore anomalous gaps)
- Matchday number within the season
- H2H average points vs this opponent over last 5 meetings (fallback to league average if < 3 meetings)

**xG conversion rate**
- Rolling actual goals / xG over last 38 games — captures over/underperformance relative to shot quality

**Elo ratings**
- K=32, base 1500, new/promoted teams start at 1400
- Ratings carry over season-to-season (no August reset)
- Pre-match Elo stored as features to avoid leakage

**Closing market odds**
- B365 and Pinnacle only — the two bookmakers present across all 11 seasons
- Overround-normalised implied probabilities (home/draw/away)

**Temporal sample weights**
- Recent seasons linearly weighted up to 1.0, oldest down to 0.1
- Used as `sample_weight` in training, not as a feature

---

## Models

**Walk-forward cross-validation** — train on all seasons up to k, validate on k+1. No shuffling, no random splits — data is strictly temporal.

| Model | Task | Details |
|---|---|---|
| LightGBM classifier | Win / draw / loss | 3-class, multiclass objective, tuned via Optuna TPE (50 trials) |
| LightGBM regressor ×2 | Home goals, away goals | L1/MAE objective, tuned via Optuna TPE (40 trials) |
| Poisson regressor ×2 | Home goals, away goals | sklearn PoissonRegressor + StandardScaler, alpha grid-searched |
| Ensemble | Both tasks | Weighted blend of LightGBM + Poisson; weights tuned separately for winner and goals |

Poisson goal rates are also converted to scoreline probabilities via full score matrix enumeration (up to 8×8), which feeds into the winner probability blend.

---

## Prediction

```python
predict("ARS", "TOT")
predict("MCI", "LIV", home_days_rest=4, away_days_rest=7)
```

Trains on the full historical dataset and returns a dict with all outputs. Accepts 3-letter codes or full team names. Falls back to default hyperparameters if Optuna tuning hasn't been run in the current kernel session.

---

## Weekly refresh

A single cell re-scrapes the current season from all four sources, then rebuilds `ml_dataset.csv` with updated Elo and odds — no manual steps. Run it every week during the season.

---

## Stack

- **Python** — pandas, numpy, scikit-learn, LightGBM, scipy
- **Scraping** — ScraperFC, Selenium (Chrome), requests, BeautifulSoup
- **Tuning** — Optuna (TPE sampler)
- **Notebook** — Jupyter (`scraper_master.ipynb`)
