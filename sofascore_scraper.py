"""
SofaScore scraper using ScraperFC.
Scrapes team stats + player stats for each available EPL season and
saves to sofascore_stats.xlsx with sheet naming:
  {YYYY-YY}_teams   (team-level)
  {YYYY-YY}_players (player-level)
"""

from pathlib import Path
import time
import random

import pandas as pd
from ScraperFC.sofascore import Sofascore

LEAGUE = "England Premier League"
OUTPUT_FILE = "sofascore_stats.xlsx"

# Desired seasons in SofaScore "YY/YY" format (2015-16 through 2024-25)
DESIRED_SEASONS = [
    "15/16", "16/17", "17/18", "18/19", "19/20",
    "20/21", "21/22", "22/23", "23/24", "24/25",
]


def _sofascore_year_to_sheet_prefix(year: str) -> str:
    """Converts '23/24' -> '2023-24' for Excel sheet name prefix."""
    parts = year.split("/")
    start_yy = int(parts[0])
    end_yy = int(parts[1])
    start_yyyy = 2000 + start_yy
    return f"{start_yyyy}-{end_yy:02d}"


def scrape_team_stats(ss: Sofascore, year: str) -> pd.DataFrame:
    """Fetches team-level league stats for one season."""
    df = ss.scrape_team_league_stats(year, LEAGUE)
    df.columns = [str(col) for col in df.columns]
    return df


def scrape_player_stats(ss: Sofascore, year: str) -> pd.DataFrame:
    """Fetches player-level league stats (total accumulation, all positions)."""
    positions = ["Goalkeepers", "Defenders", "Midfielders", "Forwards"]
    frames = []
    for pos in positions:
        try:
            df = ss.scrape_player_league_stats(
                year,
                LEAGUE,
                accumulation="total",
                selected_positions=[pos],
            )
            df["position_group"] = pos
            df.columns = [str(c) for c in df.columns]
            frames.append(df)
        except Exception as e:
            print(f"    Warning: {pos} failed: {e}")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def run_all_seasons(desired_seasons=DESIRED_SEASONS, output_file=OUTPUT_FILE):
    """Scrapes all available seasons and writes team + player sheets to Excel."""
    ss = Sofascore()

    # Get valid seasons from ScraperFC
    valid_seasons = ss.get_valid_seasons(LEAGUE)
    print(f"Valid seasons available: {list(valid_seasons.keys())}")

    seasons_to_run = [y for y in desired_seasons if y in valid_seasons]
    skipped = [y for y in desired_seasons if y not in valid_seasons]
    if skipped:
        print(f"Skipping (not available): {skipped}")

    if not seasons_to_run:
        print("No seasons to scrape.")
        return

    sheets = {}
    out_path = Path(output_file)
    
    # Auto-resume: Load existing data if file exists
    if out_path.exists():
        print(f"\n[INFO] Found existing '{output_file}'. Loading data to resume...")
        try:
            sheets = pd.read_excel(out_path, sheet_name=None)
            print(f"[INFO] Loaded {len(sheets)} existing sheets.")
        except Exception as e:
            print(f"[WARNING] Could not load existing file (starting fresh): {e}")

    for i, year in enumerate(seasons_to_run):
        prefix = _sofascore_year_to_sheet_prefix(year)
        team_sheet_name = f"{prefix}_teams"
        player_sheet_name = f"{prefix}_players"

        # Skip if both team and player sheets already exist for this season
        if team_sheet_name in sheets and player_sheet_name in sheets:
            print(f"\n[{i+1}/{len(seasons_to_run)}] Season: {year} - ALREADY SCRAPED, skipping...")
            continue

        print(f"\n[{i+1}/{len(seasons_to_run)}] Season: {year} (sheet prefix: {prefix})")

        # Team stats
        try:
            team_df = scrape_team_stats(ss, year)
            sheets[team_sheet_name] = team_df
            print(f"  Teams: {team_df.shape[0]} rows, {team_df.shape[1]} cols")
        except Exception as e:
            print(f"  Team stats ERROR: {e}")

        # Player stats
        try:
            player_df = scrape_player_stats(ss, year)
            if not player_df.empty:
                sheets[player_sheet_name] = player_df
                print(f"  Players: {player_df.shape[0]} rows, {player_df.shape[1]} cols")
            else:
                print(f"  Players: no data returned")
        except Exception as e:
            print(f"  Player stats ERROR: {e}")

        try:
            with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"  Auto-saved up to {year}")
        except PermissionError:
            print(f"  [!] Save failed: '{output_file}' is open. Please close it to allow saving after the next season.")

        if i < len(seasons_to_run) - 1:
            wait = random.uniform(3, 6)
            print(f"  Waiting {wait:.1f}s before next season...")
            time.sleep(wait)

    print(f"\nSaved {len(sheets)} sheets -> {out_path.resolve()}")
    return sheets


if __name__ == "__main__":
    run_all_seasons()
