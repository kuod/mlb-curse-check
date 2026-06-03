#!/usr/bin/env python3
"""
Fetch 10 years of MLB data from the MLB Stats API and compute luck factors.
Outputs data.json for the GitHub Pages site.
"""

import json
import math
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

SEASONS = list(range(2016, 2026))
BASE_URL = "https://statsapi.mlb.com/api/v1"

# All 30 MLB team IDs → (canonical display name, abbreviation)
CANONICAL_NAMES = {
    108: ("Los Angeles Angels", "LAA"),
    109: ("Arizona Diamondbacks", "ARI"),
    110: ("Baltimore Orioles", "BAL"),
    111: ("Boston Red Sox", "BOS"),
    112: ("Chicago Cubs", "CHC"),
    113: ("Cincinnati Reds", "CIN"),
    114: ("Cleveland Guardians", "CLE"),
    115: ("Colorado Rockies", "COL"),
    116: ("Detroit Tigers", "DET"),
    117: ("Houston Astros", "HOU"),
    118: ("Kansas City Royals", "KC"),
    119: ("Los Angeles Dodgers", "LAD"),
    120: ("Washington Nationals", "WSH"),
    121: ("New York Mets", "NYM"),
    133: ("Athletics", "ATH"),
    134: ("Pittsburgh Pirates", "PIT"),
    135: ("San Diego Padres", "SD"),
    136: ("Seattle Mariners", "SEA"),
    137: ("San Francisco Giants", "SF"),
    138: ("St. Louis Cardinals", "STL"),
    139: ("Tampa Bay Rays", "TB"),
    140: ("Texas Rangers", "TEX"),
    141: ("Toronto Blue Jays", "TOR"),
    142: ("Minnesota Twins", "MIN"),
    143: ("Philadelphia Phillies", "PHI"),
    144: ("Atlanta Braves", "ATL"),
    145: ("Chicago White Sox", "CWS"),
    146: ("Miami Marlins", "MIA"),
    147: ("New York Yankees", "NYY"),
    158: ("Milwaukee Brewers", "MIL"),
}


# team_id -> (league, division) — static across all seasons
TEAM_DIVISIONS = {
    108: ("AL", "W"),  # LAA
    109: ("NL", "W"),  # ARI
    110: ("AL", "E"),  # BAL
    111: ("AL", "E"),  # BOS
    112: ("NL", "C"),  # CHC
    113: ("NL", "C"),  # CIN
    114: ("AL", "C"),  # CLE
    115: ("NL", "W"),  # COL
    116: ("AL", "C"),  # DET
    117: ("AL", "W"),  # HOU
    118: ("AL", "C"),  # KC
    119: ("NL", "W"),  # LAD
    120: ("NL", "E"),  # WSH
    121: ("NL", "E"),  # NYM
    133: ("AL", "W"),  # ATH
    134: ("NL", "C"),  # PIT
    135: ("NL", "W"),  # SD
    136: ("AL", "W"),  # SEA
    137: ("NL", "W"),  # SF
    138: ("NL", "C"),  # STL
    139: ("AL", "E"),  # TB
    140: ("AL", "W"),  # TEX
    141: ("AL", "E"),  # TOR
    142: ("AL", "C"),  # MIN
    143: ("NL", "E"),  # PHI
    144: ("NL", "E"),  # ATL
    145: ("AL", "C"),  # CWS
    146: ("NL", "E"),  # MIA
    147: ("AL", "E"),  # NYY
    158: ("NL", "C"),  # MIL
}


def fetch_with_retry(url, params=None, retries=3):
    """Fetch a URL with exponential backoff retries."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  Retry {attempt + 1}/{retries} for {url}: {e}", file=sys.stderr)
            time.sleep(wait)


def fetch_standings(year):
    """Fetch regular season standings for a given year."""
    print(f"  Fetching standings for {year}...")
    data = fetch_with_retry(
        f"{BASE_URL}/standings",
        params={
            "leagueId": "103,104",
            "season": year,
            "standingsTypes": "regularSeason",
            "hydrate": "team",
        },
    )

    results = {}
    for record in data.get("records", []):
        for tr in record.get("teamRecords", []):
            team_id = tr["team"]["id"]
            results[team_id] = {
                "teamNameThatYear": tr["team"]["name"],
                "wins": tr["wins"],
                "losses": tr["losses"],
                "gamesPlayed": tr["gamesPlayed"],
                "runsScored": tr["runsScored"],
                "runsAllowed": tr["runsAllowed"],
            }
    return year, results


def fetch_schedule(year):
    """Fetch regular season game scores to compute close-game records."""
    print(f"  Fetching schedule for {year}...")
    data = fetch_with_retry(
        f"{BASE_URL}/schedule",
        params={
            "sportId": 1,
            "season": year,
            "gameType": "R",
            "fields": "dates,games,teams,score,status,abstractGameState,home,away,team,id",
        },
    )

    # team_id -> {closeWins, closeLosses}
    close_records = {}
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            status = game.get("status", {}).get("abstractGameState", "")
            if status != "Final":
                continue
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            home_score = home.get("score")
            away_score = away.get("score")
            if home_score is None or away_score is None:
                continue

            margin = abs(home_score - away_score)
            if margin > 2:
                continue  # not a close game

            home_id = home["team"]["id"]
            away_id = away["team"]["id"]

            if home_id not in close_records:
                close_records[home_id] = {"closeWins": 0, "closeLosses": 0}
            if away_id not in close_records:
                close_records[away_id] = {"closeWins": 0, "closeLosses": 0}

            if home_score > away_score:
                close_records[home_id]["closeWins"] += 1
                close_records[away_id]["closeLosses"] += 1
            else:
                close_records[away_id]["closeWins"] += 1
                close_records[home_id]["closeLosses"] += 1

    return year, close_records


def fetch_postseason(year):
    """Fetch postseason results and determine each team's deepest round."""
    print(f"  Fetching postseason for {year}...")
    data = fetch_with_retry(
        f"{BASE_URL}/schedule",
        params={
            "sportId": 1,
            "season": year,
            "gameType": "F,D,L,W",
            "fields": "dates,games,teams,score,status,abstractGameState,home,away,team,id,seriesDescription,gameType,seriesGameNumber,gamesInSeries",
        },
    )

    # Track series: (gameType, frozenset({team_id_a, team_id_b})) -> {team_id: wins}
    series_wins = {}

    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            status = game.get("status", {}).get("abstractGameState", "")
            if status != "Final":
                continue
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            home_score = home.get("score")
            away_score = away.get("score")
            if home_score is None or away_score is None:
                continue

            game_type = game.get("gameType", "")
            home_id = home["team"]["id"]
            away_id = away["team"]["id"]
            series_key = (game_type, frozenset({home_id, away_id}))

            if series_key not in series_wins:
                series_wins[series_key] = {home_id: 0, away_id: 0}

            if home_score > away_score:
                series_wins[series_key][home_id] += 1
            else:
                series_wins[series_key][away_id] += 1

    # Determine series winners and losers
    # Round ordering: F=1 (WC), D=2 (DS), L=3 (LCS), W=4 (WS)
    round_outcomes = {}  # team_id -> set of rounds reached

    for (game_type, teams_frozen), wins in series_wins.items():
        teams = list(teams_frozen)
        if len(teams) != 2:
            continue
        t1, t2 = teams[0], teams[1]
        w1, w2 = wins.get(t1, 0), wins.get(t2, 0)

        # Determine winner/loser only if series is clearly decided
        # (won't be equal for WC 1-game, best-of-5, best-of-7)
        if w1 > w2:
            winner, loser = t1, t2
        elif w2 > w1:
            winner, loser = t2, t1
        else:
            # Tied — shouldn't happen for completed series, but skip
            continue

        for team_id in [winner, loser]:
            if team_id not in round_outcomes:
                round_outcomes[team_id] = {}
            round_outcomes[team_id][game_type] = "won" if team_id == winner else "lost"

    # Convert to deepest playoff outcome
    outcomes = {}
    for team_id, rounds in round_outcomes.items():
        if rounds.get("W") == "won":
            outcomes[team_id] = "WS_CHAMP"
        elif rounds.get("W") == "lost":
            outcomes[team_id] = "PENNANT"
        elif rounds.get("L") == "lost":
            outcomes[team_id] = "LCS"
        elif rounds.get("D") == "lost":
            outcomes[team_id] = "DS"
        elif rounds.get("F") == "lost":
            outcomes[team_id] = "WC"
        # Teams that won WC and moved on are already captured by later rounds
        # Teams that won WC but then lost DS are captured by DS

    return year, outcomes


def compute_pythagorean_luck(wins, games_played, runs_scored, runs_allowed):
    """Pythagorean expected wins vs actual wins."""
    if runs_scored == 0 and runs_allowed == 0:
        return 0.0, 0.0
    exp = 1.83
    rs_exp = runs_scored ** exp
    ra_exp = runs_allowed ** exp
    denom = rs_exp + ra_exp
    if denom == 0:
        return 0.0, 0.0
    pyth_pct = rs_exp / denom
    pyth_expected = pyth_pct * games_played
    return round(pyth_expected, 2), round(wins - pyth_expected, 2)


def compute_close_game_luck(close_wins, close_losses, wins, games_played):
    """Close game luck: outperforming overall win% in close games."""
    close_games = close_wins + close_losses
    if close_games == 0 or games_played == 0:
        return 0.0
    close_pct = close_wins / close_games
    overall_pct = wins / games_played
    return round((close_pct - overall_pct) * close_games, 2)


def build_data():
    """Fetch all data and compute luck factors for all seasons."""
    standings_by_year = {}
    schedules_by_year = {}
    postseason_by_year = {}

    # Parallel fetch
    futures = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        for year in SEASONS:
            futures.append(("standings", executor.submit(fetch_standings, year)))
            futures.append(("schedule", executor.submit(fetch_schedule, year)))
            futures.append(("postseason", executor.submit(fetch_postseason, year)))

        for kind, future in futures:
            try:
                yr, result = future.result()
                if kind == "standings":
                    standings_by_year[yr] = result
                elif kind == "schedule":
                    schedules_by_year[yr] = result
                else:
                    postseason_by_year[yr] = result
            except Exception as e:
                print(f"Error fetching {kind}: {e}", file=sys.stderr)

    # Build team-centric data
    teams_data = []
    for team_id, (canonical_name, abbrev) in sorted(CANONICAL_NAMES.items(), key=lambda x: x[1][0]):
        seasons_data = {}
        total_luck = 0.0
        seasons_with_data = 0

        for year in SEASONS:
            standings = standings_by_year.get(year, {})
            close_rec = schedules_by_year.get(year, {})
            playoff_outcomes = postseason_by_year.get(year, {})

            team_standings = standings.get(team_id)
            if not team_standings:
                continue

            wins = team_standings["wins"]
            losses = team_standings["losses"]
            games_played = team_standings["gamesPlayed"]
            rs = team_standings["runsScored"]
            ra = team_standings["runsAllowed"]
            name_that_year = team_standings["teamNameThatYear"]

            team_close = close_rec.get(team_id, {"closeWins": 0, "closeLosses": 0})
            close_wins = team_close["closeWins"]
            close_losses = team_close["closeLosses"]

            pyth_expected, pyth_luck = compute_pythagorean_luck(wins, games_played, rs, ra)
            close_luck = compute_close_game_luck(close_wins, close_losses, wins, games_played)
            composite = round(0.6 * pyth_luck + 0.4 * close_luck, 2)

            playoff_outcome = playoff_outcomes.get(team_id, "MISSED")

            seasons_data[str(year)] = {
                "wins": wins,
                "losses": losses,
                "gamesPlayed": games_played,
                "runsScored": rs,
                "runsAllowed": ra,
                "pythExpectedWins": pyth_expected,
                "pythLuck": pyth_luck,
                "closeWins": close_wins,
                "closeLosses": close_losses,
                "closeGames": close_wins + close_losses,
                "closeLuck": close_luck,
                "compositeLuck": composite,
                "playoffOutcome": playoff_outcome,
                "teamNameThatYear": name_that_year,
            }
            total_luck += composite
            seasons_with_data += 1

        avg_luck = round(total_luck / seasons_with_data, 2) if seasons_with_data > 0 else 0.0

        league, division = TEAM_DIVISIONS.get(team_id, ("?", "?"))
        teams_data.append({
            "id": team_id,
            "name": canonical_name,
            "abbreviation": abbrev,
            "league": league,
            "division": division,
            "totalLuck": round(total_luck, 2),
            "avgLuck": avg_luck,
            "seasons": seasons_data,
        })

    return {
        "metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "seasons": SEASONS,
        },
        "teams": teams_data,
    }


def main():
    print("Fetching MLB data for 2016–2025...")
    data = build_data()

    output_path = "data.json"
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nWrote {output_path}")
    print(f"  {len(data['teams'])} teams")

    # Quick sanity check
    for team in data["teams"]:
        seasons_with_data = len(team["seasons"])
        print(f"  {team['abbreviation']}: {seasons_with_data}/10 seasons, total luck: {team['totalLuck']:+.1f}")


if __name__ == "__main__":
    main()
