# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Regenerate data.json from MLB Stats API (~15–30s)
pip install -r requirements.txt
python fetch_data.py

# Serve locally
python -m http.server 8000

# Run tests
python -m unittest discover -s tests
```

## Architecture

This is a two-stage static site:

1. **`fetch_data.py`** — fetches from the MLB Stats API and writes `data.json`. Three endpoints per season (standings, regular-season schedule, postseason schedule) fetched in parallel via `ThreadPoolExecutor`. Computes Pythagorean luck, close-game luck (≤2-run margin), and a composite score (0.6/0.4 weighted) for all 30 teams × 10 seasons. Team IDs are hardcoded in `CANONICAL_NAMES`.

2. **`index.html`** — self-contained page (no framework, no build step) that renders the table from an inlined copy of the data (`const data = {...};` in the boot IIFE; `fetch_data.py` keeps it in sync with `data.json`). All styling is inline `<style>`, all logic is inline `<script>`. Key JS functions: `luckToColor()` (HSL diverging scale), `badgeHtml()` (playoff badge), `buildTooltip()` (hover detail), `renderTable()` (full re-render on sort change).

`data.json` is committed so the site works without running the Python script. `fetch_data.py` exits non-zero and leaves files untouched if any fetch fails or the dataset is incomplete.

`index.html` also contains a hand-maintained `PAYROLL_DATA` table ($M, labelled "Opening Day" in the UI) used by the payroll scatter. It is not from the MLB Stats API. Its source and exact definition are unknown, so treat the figures as unsourced, approximate estimates; do not describe them as verified. A Baseball-Reference spot check (2026-10-19) found 39% of the 239 compared team-seasons differ by more than 10%; see the README's Data section for details. `sw.js` exists but is not currently registered by `index.html`.

## Luck Factor Formulas

```
Pythagorean expected wins = (RS^1.83 / (RS^1.83 + RA^1.83)) × GP
Pythagorean luck = actual wins − expected wins

Close-game luck = (close_win% − overall_win%) × close_games_played
  where close game = final margin ≤ 2 runs

Composite = 0.6 × pythagorean_luck + 0.4 × close_game_luck
```

## data.json Schema

```json
{
  "metadata": { "generated": "ISO-8601", "seasons": [2016..2025] },
  "teams": [{
    "id": 147, "name": "...", "abbreviation": "NYY",
    "league": "AL", "division": "E",
    "totalLuck": -7.2, "avgLuck": -0.72,
    "seasons": {
      "2025": {
        "wins", "losses", "gamesPlayed", "runsScored", "runsAllowed",
        "pythExpectedWins", "pythLuck",
        "closeWins", "closeLosses", "closeGames", "closeLuck",
        "compositeLuck", "playoffOutcome", "teamNameThatYear"
      }
    }
  }]
}
```

`playoffOutcome` values: `WS_CHAMP`, `PENNANT`, `LCS`, `DS`, `WC`, `MISSED`.

## Notes

- The 2020 season was 60 games; its column is marked `2020*` in the UI.
- Cleveland's historical name (`Indians` pre-2022, `Guardians` after) is stored in `teamNameThatYear` per season; the canonical row label always uses the current name.
- The MLB Stats API has no auth requirement and no documented rate limits. The script uses `max_workers=5` with 3-retry exponential backoff.
