"""
Weekly predictions updater.

Usage — paste this into the notebook after running predict() for each match,
or run it standalone if you have the results dicts in a list.

Example:
    results = [
        predict("ARS", "CHE"),
        predict("MCI", "LIV"),
        predict("TOT", "MUN"),
    ]
    kickoffs = [
        "2026-05-17T14:00:00Z",
        "2026-05-17T16:30:00Z",
        "2026-05-17T14:00:00Z",
    ]
    update_predictions(results, matchweek=38, season="2025-26", kickoffs=kickoffs)
"""

import json
from pathlib import Path
from datetime import date

PREDICTIONS_PATH = Path(__file__).parent / "predictions.json"

TEAM_FULL = {
    'ARS':'Arsenal', 'AVL':'Aston Villa', 'BOU':'Bournemouth', 'BRE':'Brentford',
    'BRI':'Brighton', 'BUR':'Burnley', 'CHE':'Chelsea', 'CRY':'Crystal Palace',
    'EVE':'Everton', 'FUL':'Fulham', 'IPS':'Ipswich', 'LEE':'Leeds',
    'LEI':'Leicester', 'LIV':'Liverpool', 'LUT':'Luton', 'MCI':'Man City',
    'MUN':'Man United', 'MID':'Middlesbrough', 'NEW':'Newcastle', 'NOR':'Norwich',
    'NFO':"Nott'm Forest", 'QPR':'QPR', 'SHU':'Sheffield Utd', 'SOU':'Southampton',
    'STK':'Stoke', 'SUN':'Sunderland', 'SWA':'Swansea', 'TOT':'Tottenham',
    'WAT':'Watford', 'WBA':'West Brom', 'WHU':'West Ham', 'WOL':'Wolves',
}


def update_predictions(predict_results: list, matchweek: int, season: str,
                       kickoffs: list = None):
    """
    Converts a list of predict() output dicts into predictions.json format
    and writes the file, archiving the current matchweek into past_matchweeks.

    predict_results : list of dicts returned by predict()
    matchweek       : int, e.g. 38
    season          : str, e.g. "2025-26"
    kickoffs        : optional list of ISO datetime strings, one per match
    """
    # load existing file
    if PREDICTIONS_PATH.exists():
        with open(PREDICTIONS_PATH, encoding='utf-8') as f:
            existing = json.load(f)
        past = existing.get('past_matchweeks', [])
        # archive current upcoming matches into past if they have results
        current_matches = existing.get('matches', [])
        if current_matches and existing.get('matchweek') != matchweek:
            past.append({
                'matchweek': existing['matchweek'],
                'season':    existing['season'],
                'matches':   current_matches,
            })
    else:
        past = []

    # build new matches list
    matches = []
    for i, r in enumerate(predict_results):
        m = {
            'home_team':           r['home_team'],
            'away_team':           r['away_team'],
            'home_team_full':      TEAM_FULL.get(r['home_team'], r['home_team']),
            'away_team_full':      TEAM_FULL.get(r['away_team'], r['away_team']),
            'kickoff':             kickoffs[i] if kickoffs and i < len(kickoffs) else None,
            'home_win_prob':       round(r['home_win_prob'], 4),
            'draw_prob':           round(r['draw_prob'], 4),
            'away_win_prob':       round(r['away_win_prob'], 4),
            'expected_home_goals': round(r['expected_home_goals'], 2),
            'expected_away_goals': round(r['expected_away_goals'], 2),
            'predicted_score':     r['predicted_score'],
            'top_scorelines':      r.get('top_scorelines', []),
            'home_elo':            round(r.get('home_elo', 1500), 1),
            'away_elo':            round(r.get('away_elo', 1500), 1),
            'result':              None,  # fill in after matches are played
            'actual_score':        None,
        }
        matches.append(m)

    out = {
        'matchweek':       matchweek,
        'season':          season,
        'updated':         str(date.today()),
        'matches':         matches,
        'past_matchweeks': past,
    }

    with open(PREDICTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"predictions.json updated — matchweek {matchweek}, {len(matches)} matches.")
    print(f"path: {PREDICTIONS_PATH.resolve()}")


def log_results(matchweek: int, results: list):
    """
    After matches are played, log the actual results into past_matchweeks.

    results: list of dicts with keys:
        home_team, away_team, result ('home'|'draw'|'away'), actual_score ('2-1')

    Example:
        log_results(37, [
            {'home_team': 'LIV', 'away_team': 'ARS', 'result': 'home', 'actual_score': '2-0'},
            {'home_team': 'CHE', 'away_team': 'MCI', 'result': 'away', 'actual_score': '0-3'},
        ])
    """
    with open(PREDICTIONS_PATH, encoding='utf-8') as f:
        data = json.load(f)

    # check upcoming matches first
    for m in data.get('matches', []):
        for r in results:
            if m['home_team'] == r['home_team'] and m['away_team'] == r['away_team']:
                m['result']       = r['result']
                m['actual_score'] = r.get('actual_score')

    # also check past matchweeks
    for wk in data.get('past_matchweeks', []):
        if wk['matchweek'] == matchweek:
            for m in wk['matches']:
                for r in results:
                    if m['home_team'] == r['home_team'] and m['away_team'] == r['away_team']:
                        m['result']       = r['result']
                        m['actual_score'] = r.get('actual_score')

    with open(PREDICTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"results logged for matchweek {matchweek}.")


# ── example usage (run from notebook) ────────────────────────────────────────
if __name__ == '__main__':
    print("import update_predictions and log_results from this file.")
    print("see docstrings for usage.")
