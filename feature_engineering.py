import pandas as pd
import numpy as np
import re

def create_rolling_features(input_path, output_path, window=5):
    print(f"[*] Loading '{input_path}'...")
    df = pd.read_csv(input_path)
    
    # 1. Convert to datetime avoiding warnings. Exclude missing dates ('NONE')
    df = df[df['date'] != 'NONE'].copy()
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%y', errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date').reset_index(drop=True)

    # 1-1. Clean column names (XGBoost/LightGBM cannot handle spaces, %, [, ], etc.)
    df.columns = [re.sub(r'[^A-Za-z0-9_]', '_', col) for col in df.columns]

    # 2. Create Target column: Home Win (1), Draw (0), Away Win (2)
    conditions = [
        (df['home_score'] > df['away_score']),
        (df['home_score'] == df['away_score']),
        (df['home_score'] < df['away_score'])
    ]
    df['target'] = np.select(conditions, [1, 0, 2], default=-1)

    # 3. Match-level stats available in the dataset to be converted into rolling averages
    match_stats = ['xg', 'score']

    # 4. Stack all matches per team vertically (ignoring home/away split temporarily)
    home_df = df[['date', 'season', 'home_team'] + [f'home_{s}' for s in match_stats]].copy()
    home_df.columns = ['date', 'season', 'team'] + match_stats
    home_df['is_home'] = 1

    away_df = df[['date', 'season', 'away_team'] + [f'away_{s}' for s in match_stats]].copy()
    away_df.columns = ['date', 'season', 'team'] + match_stats
    away_df['is_home'] = 0

    team_matches = pd.concat([home_df, away_df]).sort_values(['team', 'date']).reset_index(drop=True)

    # 5. Calculate rolling averages per team (CRITICAL: use shift(1) to exclude the current match)
    rolling_features = []
    for stat in match_stats:
        rolling_col = f'{stat}_rolling_{window}'
        # Calculate average of last 'window' matches; use min_periods=1 to keep early season matches
        team_matches[rolling_col] = team_matches.groupby('team')[stat].transform(
            lambda x: x.shift(1).rolling(window, min_periods=1).mean()
        )
        rolling_features.append(rolling_col)

    # 6. Merge rolling stats back to the original match schedule (Home/Away)
    home_rolling = team_matches[team_matches['is_home'] == 1][['date', 'team'] + rolling_features]
    home_rolling.columns = ['date', 'home_team'] + [f'home_{c}' for c in rolling_features]
    df = pd.merge(df, home_rolling, on=['date', 'home_team'], how='left')

    away_rolling = team_matches[team_matches['is_home'] == 0][['date', 'team'] + rolling_features]
    away_rolling.columns = ['date', 'away_team'] + [f'away_{c}' for c in rolling_features]
    df = pd.merge(df, away_rolling, on=['date', 'away_team'], how='left')

    # 7. Drop original match stats that cause Data Leakage
    leaky_columns = ['home_score', 'away_score'] + \
                    [f'home_{s}' for s in match_stats] + \
                    [f'away_{s}' for s in match_stats]

    df_ml = df.drop(columns=[col for col in leaky_columns if col in df.columns])

    # 8. Data Leakage Fix: Shift Season-level stats by 1 season (Use previous season's stats)
    base_info = ['date', 'season', 'home_team', 'away_team', 'target']
    new_rolling = [f'home_{c}' for c in rolling_features] + [f'away_{c}' for c in rolling_features]
    
    # Identify all season-level columns (FBref, Understat season, SofaScore)
    season_cols = [c for c in df_ml.columns if c not in base_info and c not in new_rolling]
    home_season_cols = [c for c in season_cols if c.startswith('home_')]
    away_season_cols = [c for c in season_cols if c.startswith('away_')]

    # Extract, sort, and shift home team stats by 1 season
    home_season_df = df_ml[['home_team', 'season'] + home_season_cols].drop_duplicates().sort_values(['home_team', 'season'])
    home_season_df[home_season_cols] = home_season_df.groupby('home_team')[home_season_cols].shift(1)
    
    # Extract, sort, and shift away team stats by 1 season
    away_season_df = df_ml[['away_team', 'season'] + away_season_cols].drop_duplicates().sort_values(['away_team', 'season'])
    away_season_df[away_season_cols] = away_season_df.groupby('away_team')[away_season_cols].shift(1)

    # Replace the leaky current-season stats with the shifted previous-season stats
    df_ml = df_ml.drop(columns=season_cols)
    df_ml = pd.merge(df_ml, home_season_df, on=['home_team', 'season'], how='left')
    df_ml = pd.merge(df_ml, away_season_df, on=['away_team', 'season'], how='left')

    # 9. Drop rows with NaN in rolling stats (e.g., very first match with no history)
    df_ml = df_ml.dropna(subset=[f'home_xg_rolling_{window}'])

    # 10. Save the final ML-ready dataset
    df_ml.to_csv(output_path, index=False)
    print("-" * 50)
    print(f"[!] Preprocessing complete: Saved to '{output_path}'")
    print(f"[!] Total matches: {len(df_ml)} | Final columns: {len(df_ml.columns)}")
    
    # Preview the most important columns for the first 5 rows
    cols_to_show = ['date', 'home_team', 'away_team', f'home_xg_rolling_{window}', f'away_xg_rolling_{window}', 'target']
    print("\n[Preview]\n", df_ml[cols_to_show].head())

if __name__ == "__main__":
    create_rolling_features("master_matches_final.csv", "ml_ready_matches.csv", window=5)
