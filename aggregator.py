import pandas as pd
import os

# ── Team name standardization ─────────────────────────────────────────────────
TEAM_CODES = {
    # Current PL teams
    "Arsenal": "ARS", "Aston Villa": "AVL", "Bournemouth": "BOU",
    "Brentford": "BRE", "Brighton": "BRI", "Brighton & Hove Albion": "BRI",
    "Chelsea": "CHE", "Crystal Palace": "CRY", "Everton": "EVE",
    "Fulham": "FUL", "Ipswich": "IPS", "Leicester": "LEI", "Leicester City": "LEI",
    "Liverpool": "LIV", "Manchester City": "MCI", "Manchester United": "MUN",
    "Manchester Utd": "MUN", "Newcastle United": "NEW", "Newcastle Utd": "NEW",
    "Nottingham Forest": "NFO", "Nott'ham Forest": "NFO", "Southampton": "SOU",
    "Tottenham": "TOT", "Tottenham Hotspur": "TOT", "West Ham": "WHU",
    "West Ham United": "WHU", "Wolverhampton Wanderers": "WOL",
    "Wolverhampton": "WOL", "Wolves": "WOL",
    # Past PL teams
    "Burnley": "BUR", "Leeds United": "LEE", "Leeds": "LEE",
    "Watford": "WAT", "Norwich City": "NOR", "Norwich": "NOR",
    "Sheffield Utd": "SHU", "Sheffield United": "SHU",
    "Huddersfield": "HUD", "Huddersfield Town": "HUD",
    "Cardiff City": "CAR", "Swansea City": "SWA", "Swansea": "SWA",
    "Stoke City": "STK", "Stoke": "STK",
    "West Brom": "WBA", "West Bromwich Albion": "WBA",
    "Sunderland": "SUN", "Middlesbrough": "MID",
    "Hull City": "HUL", "Hull": "HUL",
}

# ── Season format utilities ───────────────────────────────────────────────────

def format_season(season_str):
    """
    Normalizes all season formats to 'YY/YY'.
      '2015-16'   -> '15/16'   (Understat Excel sheet name format)
      '2022-2023' -> '22/23'   (FBref ScraperFC format)
      '23/24'     -> '23/24'   (SofaScore ScraperFC format, already correct)
    """
    s = str(season_str).strip()
    if "/" in s:
        return s
    if "-" in s:
        parts = s.split("-")
        start = parts[0][-2:]
        end = parts[1][-2:]
        return f"{start}/{end}"
    return s


def apply_compact_date(date_series):
    """Converts dates to M/D/YY without leading zeros. e.g. '08/08/2015' -> '8/8/15'"""
    dt = pd.to_datetime(date_series, errors="coerce")
    return dt.apply(lambda x: f"{x.month}/{x.day}/{x.year % 100}" if pd.notnull(x) else "NONE")


def standardize_teams(df, cols):
    """Maps full team names to 3-letter codes in the specified columns."""
    for col in cols:
        if col in df.columns:
            df[col] = df[col].map(lambda x: TEAM_CODES.get(str(x).strip(), x))
    return df


# ── Source loaders ────────────────────────────────────────────────────────────

def load_understat(file_path="understat_by_season.xlsx"):
    """
    Loads Understat Excel (Inje's scraper output).
    Sheets named: '{YYYY-YY}_season', '{YYYY-YY}_players', '{YYYY-YY}_matches'

    Returns:
        matches_df  : all match records with columns [season, date, home_team, away_team,
                      home_score, away_score, home_xg, away_xg]
        season_df   : season-level team stats [team_name, season, PPDA, xPTS, xG, xGA]
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"[Understat] File not found: '{file_path}'")

    print(f"[Understat] Loading '{file_path}'...")
    all_sheets = pd.read_excel(file_path, sheet_name=None)

    matches_list, season_list, players_list = [], [], []

    for sheet_name, df in all_sheets.items():
        raw_season = sheet_name.split("_")[0]
        season = format_season(raw_season)

        if sheet_name.endswith("_matches"):
            df["season"] = season
            df["date"] = apply_compact_date(df["date"])
            df = df.rename(columns={"home_goals": "home_score", "away_goals": "away_score"})
            matches_list.append(df)

        elif sheet_name.endswith("_season"):
            df["season"] = season
            df = df.rename(columns={"team": "team_name"})
            season_list.append(df[["team_name", "season", "PPDA", "xPTS", "xG", "xGA"]])

        elif sheet_name.endswith("_players"):
            df["season"] = season
            players_list.append(df)

    matches_df = pd.concat(matches_list, ignore_index=True)
    season_df = pd.concat(season_list, ignore_index=True)

    matches_df = standardize_teams(matches_df, ["home_team", "away_team"])
    season_df = standardize_teams(season_df, ["team_name"])

    # ── Extract Minimal Player Data (Star Player Factor) ──
    if players_list:
        players_df = pd.concat(players_list, ignore_index=True)
        if "team_title" in players_df.columns:
            # Understat team_title can have multiple teams (e.g. transferred players). Use the primary one.
            players_df["team_name"] = players_df["team_title"].astype(str).apply(lambda x: x.split(',')[0].strip())
            players_df = standardize_teams(players_df, ["team_name"])
            
            for col in ["goals", "xA"]:
                if col in players_df.columns:
                    players_df[col] = pd.to_numeric(players_df[col], errors="coerce").fillna(0)
            
            # Find the best scorer and playmaker for each team per season
            player_features = players_df.groupby(["team_name", "season"]).agg(
                top_scorer_goals=("goals", "max"),
                top_playmaker_xA=("xA", "max")
            ).reset_index()
            
            # Merge the player features into the season summary
            season_df = season_df.merge(player_features, on=["team_name", "season"], how="left")

    print(f"  -> {len(matches_df)} matches | {len(season_df)} team-season records")
    return matches_df, season_df


def load_fbref(file_path="FBref_Aggregated_Stats.xlsx"):
    """
    Loads FBref Excel (Alex's scraper output).
    Expected format: one tab per season (e.g. '2022-2023'),
    columns include 'Team'/'Squad' + stat columns from ScraperFC
    (e.g. standard_Gls, standard_xG, shooting_SoT, passing_Cmp%, defense_Tkl, ...).

    Returns:
        DataFrame with columns [team_name, season, ...all numeric metrics]
        or None if file doesn't exist.
    """
    if not os.path.exists(file_path):
        print(f"[FBref] '{file_path}' not found - skipping.")
        return None

    print(f"[FBref] Loading '{file_path}'...")
    all_sheets = pd.read_excel(file_path, sheet_name=None)

    dfs = []
    for sheet_name, df in all_sheets.items():
        # Infer season from sheet tab name (e.g. '2022-2023')
        df["season"] = format_season(sheet_name)

        # Normalize team column name
        team_col = next(
            (c for c in df.columns if c.lower() in ("team", "squad")), None
        )
        if team_col is None:
            print(f"  [!] No team column found in sheet '{sheet_name}', skipping.")
            continue
        df = df.rename(columns={team_col: "team_name"})

        dfs.append(df)

    if not dfs:
        print("  -> No valid sheets found.")
        return None

    fbref_df = pd.concat(dfs, ignore_index=True)
    fbref_df = standardize_teams(fbref_df, ["team_name"])

    # Keep team_name, season + all numeric metric columns
    numeric_cols = fbref_df.select_dtypes(include="number").columns.tolist()
    fbref_df = fbref_df[["team_name", "season"] + numeric_cols]

    print(f"  -> {len(fbref_df)} team-season records | {len(numeric_cols)} metrics")
    return fbref_df


def load_sofascore(file_path="sofascore_stats.xlsx"):
    """
    Loads SofaScore Excel (Shivanth's scraper output).
    Expected format: two tabs per season:
      '{YYYY-YY}_teams'   -> team-level league stats (used for match aggregation)
      '{YYYY-YY}_players' -> player-level stats (stored separately, not merged into matches)

    Returns:
        team_df : season-level team stats [team_name, season, ...numeric metrics]
                  or None if file doesn't exist.
    """
    if not os.path.exists(file_path):
        print(f"[SofaScore] '{file_path}' not found - skipping.")
        return None

    print(f"[SofaScore] Loading '{file_path}'...")
    all_sheets = pd.read_excel(file_path, sheet_name=None)

    team_dfs = []
    for sheet_name, df in all_sheets.items():
        if "player" in sheet_name.lower():
            continue  # Player stats not used in match aggregation

        raw_season = sheet_name.split("_")[0]
        df["season"] = format_season(raw_season)

        # Normalize team column
        team_col = next(
            (c for c in df.columns if "team" in c.lower() or "name" in c.lower()), None
        )
        if team_col is None:
            print(f"  [!] No team column found in sheet '{sheet_name}', skipping.")
            continue
        df = df.rename(columns={team_col: "team_name"})

        team_dfs.append(df)

    if not team_dfs:
        print("  -> No team-level sheets found.")
        return None

    ss_df = pd.concat(team_dfs, ignore_index=True)
    ss_df = standardize_teams(ss_df, ["team_name"])

    numeric_cols = ss_df.select_dtypes(include="number").columns.tolist()
    ss_df = ss_df[["team_name", "season"] + numeric_cols]

    print(f"  -> {len(ss_df)} team-season records | {len(numeric_cols)} metrics")
    return ss_df


# ── Merge helper ──────────────────────────────────────────────────────────────

def merge_team_stats(matches_df, stats_df, source_name):
    """
    Merges season-level team stats onto the matches dataframe.
    For each metric column in stats_df, adds:
      home_{metric}  - stat for the home team that season
      away_{metric}  - stat for the away team that season
    Joins on (team, season).
    """
    if stats_df is None:
        return matches_df

    metric_cols = [c for c in stats_df.columns if c not in ("team_name", "season")]

    # Home team merge
    home_stats = stats_df.rename(
        columns={c: f"home_{c}" for c in metric_cols} | {"team_name": "_merge_key"}
    )
    matches_df = matches_df.merge(
        home_stats,
        left_on=["home_team", "season"],
        right_on=["_merge_key", "season"],
        how="left",
    ).drop(columns=["_merge_key"])

    # Away team merge
    away_stats = stats_df.rename(
        columns={c: f"away_{c}" for c in metric_cols} | {"team_name": "_merge_key"}
    )
    matches_df = matches_df.merge(
        away_stats,
        left_on=["away_team", "season"],
        right_on=["_merge_key", "season"],
        how="left",
    ).drop(columns=["_merge_key"])

    print(f"[{source_name}] Merged {len(metric_cols)} metrics -> {len(metric_cols) * 2} columns added (home + away)")
    return matches_df


# ── Main aggregation ──────────────────────────────────────────────────────────

def aggregate_master(
    understat_file="understat_by_season.xlsx",
    fbref_file="FBref_Aggregated_Stats.xlsx",
    sofascore_file="sofascore_stats.xlsx",
    output_file="master_matches_final.csv",
):
    """
    Cross-source aggregator. Builds one master matches DataFrame from:
      - Understat   : base match records + season-level xG/PPDA/xPTS stats  [required]
      - FBref       : season-level squad stats per team                      [optional]
      - SofaScore   : season-level team league stats per team                [optional]

    Output: one row per match, all available metrics as home_* and away_* columns.
    """
    # ── 1. Understat (base)
    matches, understat_season = load_understat(understat_file)

    # Dynamically pick up all season metrics including the new player stats
    us_metrics = [c for c in understat_season.columns if c not in ("team_name", "season")]

    # Merge Understat season stats for home team
    home_rename = {"team_name": "_merge_key"}
    home_rename.update({m: f"home_season_{m}" for m in us_metrics})
    home_us = understat_season.rename(columns=home_rename)
    matches = matches.merge(
        home_us,
        left_on=["home_team", "season"], right_on=["_merge_key", "season"],
        how="left",
    ).drop(columns=["_merge_key"])

    # Merge Understat season stats for away team
    away_rename = {"team_name": "_merge_key"}
    away_rename.update({m: f"away_season_{m}" for m in us_metrics})
    away_us = understat_season.rename(columns=away_rename)
    matches = matches.merge(
        away_us,
        left_on=["away_team", "season"], right_on=["_merge_key", "season"],
        how="left",
    ).drop(columns=["_merge_key"])

    print(f"[Understat] Merge complete: {matches.shape}")

    # ── 2. FBref (optional)
    fbref_df = load_fbref(fbref_file)
    matches = merge_team_stats(matches, fbref_df, "FBref")

    # ── 3. SofaScore (optional)
    ss_df = load_sofascore(sofascore_file)
    matches = merge_team_stats(matches, ss_df, "SofaScore")

    # ── 4. Drop redundant raw columns from Understat source
    matches = matches.drop(columns=[c for c in ("score",) if c in matches.columns])

    # ── 5. Column ordering: base columns first, then all added stats
    base_cols = [
        "season", "date", "home_team", "away_team",
        "home_score", "away_score", "home_xg", "away_xg",
    ]
    remaining = [c for c in matches.columns if c not in base_cols]
    ordered_cols = [c for c in base_cols if c in matches.columns] + remaining
    matches = matches[ordered_cols]

    # ── 6. Save (Let pandas handle missing values natively as empty/NaN)
    matches.to_csv(output_file, index=False, na_rep="NaN")

    print("-" * 55)
    print(f"SUCCESS: {len(matches)} matches | {len(matches.columns)} columns")
    print(f"Saved to: '{output_file}'")
    print(f"Columns: {list(matches.columns)}")


if __name__ == "__main__":
    aggregate_master()
