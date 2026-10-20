# MLB Luck Factor 2016–2025

A static GitHub Pages site that quantifies how "lucky" each MLB team was each season, using two independent luck signals combined into a single composite score.

Live site: *(enable GitHub Pages on `main` / root after pushing)*

## What is the Luck Factor?

The composite luck score is expressed in **wins above or below expectation**. Positive = luckier than underlying performance suggests; negative = unluckier.

### 1. Pythagorean Luck (60% weight)

Based on Bill James's Pythagorean expectation: a team's run differential predicts their win percentage better than their actual record does over the long run.

```
Expected wins = (RS^1.83 / (RS^1.83 + RA^1.83)) × games played
Pythagorean luck = Actual wins − Expected wins
```

A team that scores lots of runs in blowouts but loses close games will have a high run differential yet win fewer games than predicted — making them look "unlucky" by this metric.

### 2. Close-Game Luck (40% weight)

Close games (decided by ≤2 runs) have a large random component. Teams that consistently win or lose them more than their overall record predicts are likely benefiting from (or suffering from) luck.

```
Close-game luck = (close-game win% − overall win%) × close games played
```

### Composite

```
Composite luck = 0.6 × Pythagorean luck + 0.4 × close-game luck
```

Both components are in the same units (wins), so they combine directly.

## The Table

| Column | Meaning |
|--------|---------|
| Each season cell | Composite luck score, color-coded red (unlucky) → white → green (lucky) |
| Playoff badge | Deepest postseason round reached that year |
| Total | Sum of composite luck across all 10 seasons (2016–2025) |
| Avg/Yr | Average composite luck per season |

Year headers are clickable to sort the table by that season's luck score.

### Playoff Badges

| Badge | Meaning |
|-------|---------|
| **WS** (gold) | Won the World Series |
| **AL / NL** (silver) | Won the pennant, lost the World Series |
| **LCS** (orange) | Won the Division Series, lost the LCS |
| **DS** (blue) | Reached the Division Series, eliminated there |
| **WC** (purple) | Reached the Wild Card round, eliminated there |
| *(none)* | Missed the playoffs |

Hover over any cell for a full breakdown: record, RS/RA, Pythagorean expected wins, close-game record, and all luck components.

## Scatter Plot

The **Scatter Plot** tab lets you visualize the relationship between luck and outcomes across seasons. Choose any two metrics for the X and Y axes to explore correlations.

## Data

All data is fetched from the **MLB Stats API** (free, public, no authentication required):

- Standings → wins, losses, runs scored, runs allowed
- Regular season schedule → game-by-game scores for close-game calculation
- Postseason schedule → bracket results for playoff outcome classification

**Payroll figures are unsourced estimates.** The payroll scatter uses a hand-entered table (`PAYROLL_DATA` in `index.html`) whose original source was not recorded; it is not from the MLB Stats API. A spot check on 2026-10-19 against Baseball-Reference's team "Est. Payroll" column (`https://www.baseball-reference.com/leagues/majors/<year>-misc.shtml`, years 2016-2019 and 2021-2025, 239 team-seasons) found only rough agreement: mean absolute difference about $12.5M, and 94 of 239 values differ by more than 10% (e.g. 2016 TEX 161.2 vs 212.1, 2019 TOR 112.0 vs 62.2, 2017 SD 34.6 vs 49.2). Opening-day, season-end and luxury-tax payrolls are defined differently, and Baseball-Reference's figure is itself an estimate, so differences are not all errors; but the table cannot be verified against any one source and no values were changed. Spotrac and The Baseball Cube could not be fetched (HTTP 402/403) so were not checked. Treat payroll as approximate. Luck and standings data come from the API.

The 2020 column is marked with `*` — that was a 60-game season, so luck values carry higher variance than normal years.

## Regenerating Data

```bash
pip install -r requirements.txt
python fetch_data.py
```

This fetches ~30 API calls (standings + schedule + postseason for each of 10 seasons) using a thread pool and writes `data.json` (and updates the inlined copy in `index.html`); it aborts without writing if any call fails. Takes about 15–30 seconds.

## Running Locally

```bash
python -m http.server 8000
# open http://localhost:8000
```

The site is a single `index.html` file with the data inlined; `python fetch_data.py` rewrites both `data.json` and the inlined copy. No build step required. `sw.js` (an offline cache) is present but not currently registered. Run tests with `python -m unittest discover -s tests`.

## Deploying to GitHub Pages

1. Push this repo to GitHub
2. Go to **Settings → Pages**
3. Set source to `main` branch, root folder
4. GitHub Pages will serve `index.html` directly
