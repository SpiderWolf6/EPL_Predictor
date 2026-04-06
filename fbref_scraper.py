"""
FBref scraper using ScraperFC.
Scrapes all squad/opponent stat categories for each EPL season and
saves one sheet per season to FBref_Aggregated_Stats.xlsx.
"""

import time
import random
from pathlib import Path

import pandas as pd
from ScraperFC.fbref import FBref

LEAGUE = "England Premier League"
# 2015-16 through 2024-25
SEASONS = list(range(2015, 2025))
OUTPUT_FILE = "FBref_Aggregated_Stats.xlsx"

TEAM_CODES = {
    "Arsenal": "ARS", "Aston Villa": "AVL", "Bournemouth": "BOU",
    "Brentford": "BRE", "Brighton": "BRI", "Brighton & Hove Albion": "BRI",
    "Chelsea": "CHE", "Crystal Palace": "CRY", "Everton": "EVE",
    "Fulham": "FUL", "Ipswich": "IPS", "Leicester": "LEI", "Leicester City": "LEI",
    "Liverpool": "LIV", "Manchester City": "MCI", "Manchester United": "MUN",
    "Manchester Utd": "MUN", "Newcastle United": "NEW", "Newcastle Utd": "NEW",
    "Nottingham Forest": "NFO", "Nott'ham Forest": "NFO", "Nott'm Forest": "NFO",
    "Southampton": "SOU", "Tottenham": "TOT", "Tottenham Hotspur": "TOT",
    "West Ham": "WHU", "West Ham United": "WHU",
    "Wolverhampton Wanderers": "WOL", "Wolverhampton": "WOL", "Wolves": "WOL",
    "Burnley": "BUR", "Leeds United": "LEE", "Leeds": "LEE",
    "Watford": "WAT", "Norwich City": "NOR", "Norwich": "NOR",
    "Sheffield Utd": "SHU", "Sheffield United": "SHU",
    "Luton Town": "LUT", "Luton": "LUT",
    "Huddersfield": "HUD", "Huddersfield Town": "HUD",
    "Cardiff City": "CAR", "Swansea City": "SWA", "Swansea": "SWA",
    "Stoke City": "STK", "Stoke": "STK",
    "West Brom": "WBA", "West Bromwich Albion": "WBA",
    "Sunderland": "SUN", "Middlesbrough": "MID",
    "Hull City": "HUL", "Hull": "HUL",
}


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            "_".join([str(c) for c in col if "Unnamed" not in str(c)]).strip()
            for col in df.columns
        ]
    else:
        df.columns = [str(c) for c in df.columns]
    df.columns = [c.replace("__", "_").strip("_") for c in df.columns]
    return df


def scrape_fbref_season(season_start_year: int) -> pd.DataFrame:
    """Scrapes all stat categories for one EPL season via ScraperFC FBref."""
    season_str = f"{season_start_year}-{season_start_year + 1}"
    print(f"  Scraping FBref: {season_str}")

    fb = FBref(wait_time=7)
    all_stats = fb.scrape_all_stats(season_str, LEAGUE)

    master_df = None

    for stat_category, tables in all_stats.items():
        if not isinstance(tables, dict):
            continue

        squad_df = tables.get("squad")
        opp_df = tables.get("opponent")

        if not isinstance(squad_df, pd.DataFrame) or not isinstance(opp_df, pd.DataFrame):
            continue

        squad_df = _clean_columns(squad_df.copy())
        opp_df = _clean_columns(opp_df.copy())

        if squad_df is None or opp_df is None:
            continue
        if "Squad" not in squad_df.columns or "Squad" not in opp_df.columns:
            continue

        squad_df = squad_df.rename(columns={"Squad": "Team"})
        opp_df = opp_df.rename(columns={"Squad": "Team"})
        opp_df["Team"] = opp_df["Team"].str.replace("vs ", "", regex=False)

        squad_df = squad_df.rename(
            columns={col: f"{stat_category}_{col}" for col in squad_df.columns if col != "Team"}
        )
        opp_df = opp_df.rename(
            columns={col: f"{stat_category}_opp_{col}" for col in opp_df.columns if col != "Team"}
        )

        combined = squad_df.merge(opp_df, on="Team", how="left")

        if master_df is None:
            master_df = combined
        else:
            overlapping = set(master_df.columns).intersection(combined.columns) - {"Team"}
            if overlapping:
                combined = combined.drop(columns=list(overlapping))
            master_df = master_df.merge(combined, on="Team", how="left")

    if master_df is None:
        return None

    master_df["Season"] = season_str
    master_df = master_df.reset_index(drop=True)
    master_df = master_df.apply(pd.to_numeric, errors="ignore")

    # Standardize team codes
    master_df["Team"] = master_df["Team"].map(
        lambda x: TEAM_CODES.get(str(x).strip(), str(x).strip())
    )

    return master_df


def run_all_seasons(seasons=SEASONS, output_file=OUTPUT_FILE):
    """Scrapes all seasons and writes one Excel sheet per season."""
    results = {}
    out_path = Path(output_file)

    # Auto-resume: Load existing data if file exists
    if out_path.exists():
        print(f"\n[INFO] Found existing '{output_file}'. Loading data to resume...")
        try:
            results = pd.read_excel(out_path, sheet_name=None)
            print(f"[INFO] Loaded {len(results)} existing seasons.")
        except Exception as e:
            print(f"[WARNING] Could not load existing file (starting fresh): {e}")

    for i, year in enumerate(seasons):
        season_str = f"{year}-{year + 1}"

        # Skip if already scraped
        if season_str in results:
            print(f"\n[{i+1}/{len(seasons)}] Season: {season_str} - ALREADY SCRAPED, skipping...")
            continue

        print(f"\n[{i+1}/{len(seasons)}] Season: {season_str}")
        try:
            df = scrape_fbref_season(year)
            if df is None or df.empty:
                print(f"  No data returned for {season_str}")
                continue
            results[season_str] = df
            print(f"  OK: {df.shape[0]} teams, {df.shape[1]} columns")
        except Exception as e:
            print(f"  ERROR: {e}")

        try:
            with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
                for s_str, d in results.items():
                    d.to_excel(writer, sheet_name=s_str, index=False)
            print(f"  Auto-saved up to {season_str}")
        except PermissionError:
            print(f"  [!] Save failed: '{output_file}' is open. Please close it to allow saving after the next season.")

        # Rate limiting between seasons
        if i < len(seasons) - 1:
            wait = random.uniform(8, 14)
            print(f"  Waiting {wait:.1f}s...")
            time.sleep(wait)

    print(f"\nSaved {len(results)} seasons -> {out_path.resolve()}")
    return results


if __name__ == "__main__":
    run_all_seasons()
