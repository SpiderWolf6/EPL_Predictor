"""
Understat scraper using ScraperFC.
Scrapes team season stats, player stats, and match stats for the EPL.
Saves to understat_by_season.xlsx.
"""

import time
from pathlib import Path

import pandas as pd
from ScraperFC.understat import Understat

LEAGUE = "EPL"
# 2015-16 through 2024-25
SEASONS = list(range(2015, 2025))
OUTPUT_FILE = "understat_by_season.xlsx"


def run_all_seasons(seasons=SEASONS, output_file=OUTPUT_FILE):
    un = Understat()
    results = {}
    out_path = Path(output_file)

    # Auto-resume: Load existing data if file exists
    if out_path.exists():
        print(f"\n[INFO] Found existing '{output_file}'. Loading data to resume...")
        try:
            results = pd.read_excel(out_path, sheet_name=None)
            print(f"[INFO] Loaded {len(results)} existing sheets.")
        except Exception as e:
            print(f"[WARNING] Could not load existing file (starting fresh): {e}")

    for i, year in enumerate(seasons):
        # Formats year to aggregator expected format: 'YYYY-YY' (e.g., '2015-16')
        season_str = f"{year}-{str(year + 1)[-2:]}"

        # Check if all 3 sheets for this season exist
        expected_sheets = [f"{season_str}_season", f"{season_str}_matches", f"{season_str}_players"]
        if all(sheet in results for sheet in expected_sheets):
            print(f"\n[{i+1}/{len(seasons)}] Season: {season_str} - ALREADY SCRAPED, skipping...")
            continue

        print(f"\n[{i+1}/{len(seasons)}] Season: {season_str}")

        # 1. Season Stats (League Table)
        try:
            season_df = un.scrape_league_table(year, LEAGUE)
            if season_df is not None and not season_df.empty:
                # Rename columns to match what aggregator.py expects
                rename_map = {"xpts": "xPTS", "ppda_coef": "PPDA", "ppda": "PPDA"}
                season_df = season_df.rename(columns=rename_map)
                results[f"{season_str}_season"] = season_df
                print(f"  Season: {season_df.shape[0]} teams")
        except Exception as e:
            print(f"  Season stats ERROR: {e}")

        # 2. Match Stats
        try:
            matches_df = un.scrape_matches(year, LEAGUE)
            if matches_df is not None and not matches_df.empty:
                # Rename xG columns so they perfectly align with aggregator.py base columns
                matches_df = matches_df.rename(columns={"home_xG": "home_xg", "away_xG": "away_xg"})
                results[f"{season_str}_matches"] = matches_df
                print(f"  Matches: {matches_df.shape[0]} matches")
        except Exception as e:
            print(f"  Matches stats ERROR: {e}")

        # 3. Player Stats
        try:
            players_df = un.scrape_players(year, LEAGUE)
            if players_df is not None and not players_df.empty:
                results[f"{season_str}_players"] = players_df
                print(f"  Players: {players_df.shape[0]} players")
        except Exception as e:
            print(f"  Player stats ERROR: {e}")

        # Auto-save after each season is fetched
        try:
            with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
                for sheet_name, df in results.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"  Auto-saved up to {season_str}")
        except PermissionError:
            print(f"  [!] Save failed: '{output_file}' is open. Please close it to allow saving after the next season.")

        # A brief pause to be polite to the Understat servers
        time.sleep(3)

    print(f"\nSaved {len(results)} sheets -> {out_path.resolve()}")
    return results


if __name__ == "__main__":
    run_all_seasons()