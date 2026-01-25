import requests
import pandas as pd
from bs4 import BeautifulSoup, Comment
from io import StringIO
from typing import Dict
import time
import random
from pathlib import Path

TEAM_CODES = {
    "Arsenal": "ARS", "Aston Villa": "AVL", "Bournemouth": "BOU", 
    "Brentford": "BRE", "Brighton": "BRI", "Burnley": "BUR", 
    "Chelsea": "CHE", "Crystal Palace": "CRY", "Everton": "EVE", 
    "Fulham": "FUL", "Liverpool": "LIV", "Manchester City": "MCI", 
    "Manchester Utd": "MUN", "Newcastle Utd": "NEW", "Nott'm Forest": "NFO", 
    "Southampton": "SOU", "Tottenham": "TOT", "West Ham": "WHU", 
    "Wolves": "WOL", "Leicester City": "LEI", "Leeds United": "LEE",
    "Sheffield Utd": "SHU", "Luton Town": "LUT", "Watford": "WAT",
    "Norwich City": "NOR", "West Brom": "WBA", "Swansea City": "SWA"
}
MISSING_VALUE = "NONE"

def merge_fbref_tables(table_dict):
    master = None
    for key, df in table_dict.items():
        df = df.copy()
        if "Squad" not in df.columns:
            continue
        
        if key.endswith("against"):
            df["Squad"] = df["Squad"].astype(str).str.replace("vs ", "", regex=False)
            df.columns = ["Squad" if c == "Squad" else f"vs_{c}" for c in df.columns]

        df = df.loc[:, ~df.columns.duplicated()]

        if master is None:
            master = df
            continue

        overlapping = set(master.columns).intersection(df.columns) - {"Squad"}
        if overlapping:
            df = df.drop(columns=list(overlapping))

        master = master.merge(df, on="Squad", how="outer")
        master = master.loc[:, ~master.columns.duplicated()]
    return master

def scrape_fbref(season_start_year: int):
    season_str = f"{season_start_year}-{season_start_year + 1}"
    url = f"https://fbref.com/en/comps/9/{season_str}/{season_str}-Premier-League-Stats"

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://fbref.com/en/",
    })
    
    print(f"Fetching: {url}")
    r = s.get(url, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    tables = {}

    def extract(div):
        table = div.find("table")
        if not table: return
        table_id = div.get("id", "unknown").replace("div_", "")

        try:
            if table_id.startswith("results") and "overall" in table_id:
                df = pd.read_html(StringIO(str(table)), header=0)[0]
                if df.columns[0].startswith("Rk_"):
                    df.columns = [c.split("_")[-1] for c in df.columns]
            else:
                df = pd.read_html(StringIO(str(table)), header=[0,1])[0]
                if isinstance(df.columns, pd.MultiIndex):
                    new_cols = []
                    for top, bottom in df.columns:
                        if "Unnamed" in str(top): new_cols.append(bottom)
                        else: new_cols.append(f"{top}_{bottom}")
                    df.columns = new_cols
        except Exception as e:
            print(f"  Failed to read {table_id}: {e}")
            return

        tables[table_id] = df
        print(f"  Extracted: {table_id}")

    for div in soup.find_all("div", class_="table_container"):
        extract(div)

    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        if 'table_container' in comment:
            sub = BeautifulSoup(comment, "html.parser")
            for div in sub.find_all("div", class_="table_container"):
                extract(div)

    return merge_fbref_tables(tables)

#aggregate
def to_team_code(name: str) -> str:
    if not isinstance(name, str): return MISSING_VALUE
    clean_name = name.replace("vs ", "").strip()
    return TEAM_CODES.get(clean_name, MISSING_VALUE)

def aggregate_fbref_seasons(years_list):
    all_season_dfs = {}

    for year in years_list:
        season_label = f"{year}-{(year + 1) % 100:02d}"
        print(f"\n--- Processing Season: {season_label} ---")
        
        try:
            mega_df = scrape_fbref(year)
            
            if mega_df is None or mega_df.empty:
                print(f" No data for {season_label}")
                continue

            # Standardization
            df = mega_df.copy()
            if "Squad" in df.columns:
                df.rename(columns={"Squad": "team"}, inplace=True)
            
            df["team"] = df["team"].apply(to_team_code)
            
            # Numeric cleaning
            df = df.replace(',', '', regex=True)
            df = df.fillna(MISSING_VALUE)

            all_season_dfs[season_label] = df
            print(f"✅ Success: {season_label} ({df.shape[1]} metrics collected)")

            if year != years_list[-1]:
                sleep_time = random.uniform(6, 10)
                print(f"Waiting {sleep_time:.1f}s to avoid block...")
                time.sleep(sleep_time)

        except Exception as e:
            print(f"❌ Error in {season_label}: {e}")
            continue

    return all_season_dfs


if __name__ == "__main__":
    SEASONS_TO_RUN = [2022, 2023]
    
    fb_data = aggregate_fbref_seasons(SEASONS_TO_RUN)

    if fb_data:
        output_path = Path("FBref_Aggregated_Stats.xlsx")
        with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
            for season, df in fb_data.items():
                df.to_excel(writer, sheet_name=season, index=False)
        print(f"\n preadsheet saved to: {output_path.resolve()}")
    else:
        print("\nNo data was collected. Check for 403 errors in the log.")
