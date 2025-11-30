import requests
import pandas as pd
from bs4 import BeautifulSoup, Comment
from typing import Dict

def scrape_fbref(year: int) -> Dict[str, pd.DataFrame]:
    """
    Scrapes all standard and advanced statistics tables from the FBref 
    Premier League season page for a given year.

    Args:
        year: The final year of the Premier League season (e.g., 2023 for 2022-2023).

    Returns:
        A dictionary where keys are table IDs (e.g., 'standings', 'stats_shooting') 
        and values are Pandas DataFrames.
    """
    url = f"https://fbref.com/en/comps/9/{year}/{year}-Premier-League-Stats"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
    }
    all_tables = {}
    
    print(f"Fetching data for the {year-1}-{year} season from: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Catches 403/404/500 errors
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for element in soup.find_all(text=lambda t: isinstance(t, Comment)):
            if 'div class="table_container" id=' in element:
                comment_soup = BeautifulSoup(element, 'html.parser')
                table_tag = comment_soup.find('table')
                
                if table_tag:
                    table_id = table_tag.parent.get('id', 'unknown').replace('div_', '')
                    df_list = pd.read_html(str(table_tag), header=1)
                    
                    if df_list:
                        df = df_list[0]
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = ['_'.join(filter(None, map(str, col))).replace('Unnamed: ', '').strip('_') for col in df.columns.values]
                        
                        all_tables[table_id] = df
                        print(f"  - Extracted: {table_id}")

        result = {}
        main_key = next((k for k in all_tables if 'standings' in k), None)
        
        if main_key:
            result['main_standings_table'] = all_tables.pop(main_key)
            
        result.update(all_tables)
        
        return result

    except requests.exceptions.HTTPError as e:
        print(f"Error while accessing FBref (HTTP Error {e.response.status_code}): {e}")
    except requests.exceptions.RequestException as e:
        print(f"An unexpected error occurred during scraping: {e}")
        
    return {}

if __name__ == "__main__":
    season_year = 2024 
    prem_stats = scrape_fbref(season_year)

    print(f"\n✅ Successfully retrieved **{len(prem_stats)}** tables.")

    if 'main_standings_table' in prem_stats:
        print("\n--- Main League Standings (Head) ---")
        print(prem_stats['main_standings_table'].head())
    
    if 'stats_shooting' in prem_stats:
        print("\n--- Shooting Stats (Head) ---")
        print(prem_stats['stats_shooting'].head())
