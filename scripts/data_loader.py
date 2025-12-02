import re
import pandas as pd
import sys

def get_export_url(url):
    """Converts a Google Sheet URL to a CSV export URL, correctly handling the gid."""
    # The gid is often at the end of the URL after #gid=
    match_gid = re.search(r'#gid=(\d+)', url)
    if not match_gid:
        # If not found after #, try to find it as a query parameter
        match_gid = re.search(r'[?&]gid=(\d+)', url)

    gid = match_gid.group(1) if match_gid else None

    # The document ID is between /d/ and /
    match_doc_id = re.search(r'/d/([^/]+)/', url)
    if not match_doc_id:
        return None # Cannot proceed without a document ID
    
    doc_id = match_doc_id.group(1)

    if gid:
        return f'https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}'
    else:
        # If no GID is found, it will export the first/default sheet.
        print(f"Warning: No GID found for URL {url}. Exporting the default sheet.")
        return f'https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv'

import numpy as np
import os
import json

# --- Caching Helper Functions ---
def _read_cache_manifest(cache_dir):
    manifest_path = os.path.join(cache_dir, 'cache_info.json')
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, 'r') as f:
            data = json.load(f)
            return data.get('last_run_most_recent')
    except (json.JSONDecodeError, IOError):
        return None

def _write_cache_manifest(cache_dir, most_recent_season):
    manifest_path = os.path.join(cache_dir, 'cache_info.json')
    try:
        with open(manifest_path, 'w') as f:
            json.dump({'last_run_most_recent': most_recent_season}, f)
    except IOError:
        print("Warning: Could not write to cache manifest file.")

def load_all_seasons():
    """Loads all seasons' data, adding a 'GameType' column and caching raw downloads."""
    season_data = {}
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gamelogs_path = os.path.join(script_dir, '..', 'data', 'gamelogs.txt')
    cache_dir = os.path.join(script_dir, '..', 'data', 'cache')
    raw_data_cache_dir = os.path.join(cache_dir, 'raw_gamelogs')
    if not os.path.exists(raw_data_cache_dir):
        os.makedirs(raw_data_cache_dir)

    try:
        with open(gamelogs_path, 'r') as f:
            gamelogs = f.readlines()
    except FileNotFoundError:
        print(f"Error: Could not find gamelogs.txt at {gamelogs_path}")
        return None

    # Determine season transition for cache invalidation
    previous_most_recent = _read_cache_manifest(cache_dir)
    season_lines = [line.strip().split('\t') for line in gamelogs if line.strip()]
    all_season_names = [parts[0] for parts in season_lines if len(parts) > 0]
    if all_season_names:
        most_recent_season_num = max([int(s.replace('S', '')) for s in all_season_names])
        most_recent_season = f"S{most_recent_season_num}"
    else:
        most_recent_season = ""

    seasons_to_recalc = []
    if most_recent_season != previous_most_recent and previous_most_recent is not None:
        print(f"New season detected. Invalidating raw data cache for {previous_most_recent}...")
        seasons_to_recalc.append(previous_most_recent)

    for log in gamelogs:
        parts = log.strip().split('\t')
        if len(parts) != 3:
            continue

        season, num_games_str, url = parts
        force_recalc = (season == most_recent_season) or (season in seasons_to_recalc)
        raw_cache_path = os.path.join(raw_data_cache_dir, f'raw_gamelog_{season}.csv')

        df = None
        if os.path.exists(raw_cache_path) and not force_recalc:
            try:
                df = pd.read_csv(raw_cache_path)
                print(f"Loaded {season} data from local cache.")
            except Exception as e:
                print(f"Error loading {season} from cache: {e}. Re-downloading...")
                df = None

        if df is None:
            export_url = get_export_url(url)
            if export_url:
                try:
                    print(f"Downloading data for {season}...")
                    df = pd.read_csv(export_url)
                    df.to_csv(raw_cache_path, index=False)
                except Exception as e:
                    print(f"Error loading data for {season} from URL: {e}")
                    continue
            else:
                print(f"Could not generate export URL for {url}")
                continue
        
        if df is not None:
            try:
                num_games = int(num_games_str)
                if 'Session' in df.columns:
                    df['GameType'] = np.where(df['Session'] <= num_games, 'Regular', 'Playoff')
                    season_data[season] = df
                else:
                    print(f"Warning: 'Session' column not found for {season}.")
            except ValueError:
                print(f"Warning: Invalid number of games for season '{season}'.")

    _write_cache_manifest(cache_dir, most_recent_season)
    return season_data, most_recent_season, [most_recent_season] + seasons_to_recalc if most_recent_season else seasons_to_recalc

def load_player_id_map():
    """Loads player ID mapping from player_id_map.json."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    player_id_map_path = os.path.join(script_dir, '..', 'docs', 'data', 'player_id_map.json')
    
    if not os.path.exists(player_id_map_path):
        print(f"Error: player_id_map.json not found at {player_id_map_path}")
        return {}

    with open(player_id_map_path, 'r') as f:
        player_id_map_raw = json.load(f)

    name_to_id_map = {}
    for player_id, player_info in player_id_map_raw.items():
        # Ensure player_id is treated as an integer for consistency later
        player_id_int = int(player_id)
        current_name = player_info['currentName'].lower()
        name_to_id_map[current_name] = player_id_int
        for former_name in player_info['formerNames']:
            name_to_id_map[former_name.lower()] = player_id_int
    return name_to_id_map

def load_player_types(force_seasons=None):
    """Loads all player type data from the sheets specified in player_types.txt."""
    player_type_data = {}
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    player_types_path = os.path.join(script_dir, '..', 'data', 'player_types.txt')
    cache_dir = os.path.join(script_dir, '..', 'data', 'cache', 'raw_player_types')
    static_player_types_dir = os.path.join(script_dir, '..', 'data', 'static_player_types')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    name_to_id_map = load_player_id_map() # Load the player ID map

    seasons_to_process = []
    # Load seasons from player_types.txt (S4 onwards)
    try:
        with open(player_types_path, 'r') as f:
            player_type_sheets = f.readlines()
            for line in player_type_sheets:
                parts = line.strip().split('\t')
                if len(parts) == 2:
                    seasons_to_process.append({'season': parts[0], 'url': parts[1], 'source': 'url'})
    except FileNotFoundError:
        print(f"Info: Could not find player_types.txt at {player_types_path}. Skipping remote player types.")

    # Add S1, S2, S3 from static CSV files
    for s_num in [1, 2, 3]:
        season_str = f'S{s_num}'
        static_csv_path = os.path.join(static_player_types_dir, f'raw_player_types_{season_str}.csv')
        if os.path.exists(static_csv_path):
            seasons_to_process.append({'season': season_str, 'path': static_csv_path, 'source': 'static_csv'})
        else:
             print(f"Info: Static player type file not found for {season_str} at {static_csv_path}. Skipping.")

    seasons_to_process.sort(key=lambda x: int(x['season'].replace('S', '')))

    force_seasons = force_seasons or []

    for item in seasons_to_process:
        season = item['season']
        force_recalc = season in force_seasons
        raw_cache_path = os.path.join(cache_dir, f'raw_player_types_{season}.csv')

        df = None
        # Attempt to load from cache
        if os.path.exists(raw_cache_path) and not force_recalc:
            try:
                df = pd.read_csv(raw_cache_path, dtype={'Player ID': str}) # Read Player ID as string
                print(f"Loaded {season} player types from local cache.")
            except Exception as e:
                print(f"Error loading {season} player types from cache: {e}. Re-loading...")
                df = None

        # If not in cache or forced, load from source
        if df is None:
            if item['source'] == 'url':
                url = item['url']
                export_url = get_export_url(url)
                if export_url:
                    try:
                        print(f"Downloading player types for {season}...")
                        df = pd.read_csv(export_url)
                        df.to_csv(raw_cache_path, index=False)
                    except Exception as e:
                        print(f"Error loading player types for {season} from URL: {e}")
                        continue
                else:
                    print(f"Could not generate export URL for {url}")
                    continue
            elif item['source'] == 'static_csv':
                csv_path = item['path']
                try:
                    print(f"Loading player types for {season} from static CSV '{csv_path}'...")
                    df = pd.read_csv(csv_path)
                    
                    # Convert 'Player ID' to numeric, coercing errors to NaN
                    df['Player ID'] = pd.to_numeric(df['Player ID'], errors='coerce')

                    # Only map names to IDs for rows where 'Player ID' is currently NaN
                    missing_id_mask = df['Player ID'].isna()
                    if missing_id_mask.any():
                        df.loc[missing_id_mask, 'Player ID'] = df.loc[missing_id_mask, 'Name'].str.lower().map(name_to_id_map)

                    unmatched_names = df[df['Player ID'].isna()]['Name'].unique()
                    if len(unmatched_names) > 0:
                        print(f"Warning: Unmatched player names in {season} from CSV: {unmatched_names}")
                    df.to_csv(raw_cache_path, index=False)
                except Exception as e:
                    print(f"Error loading player types for {season} from static CSV: {e}")
                    continue
        
        if df is not None:
            # Ensure 'Player ID' is integer type for consistency
            if 'Player ID' in df.columns:
                df['Player ID'] = pd.to_numeric(df['Player ID'], errors='coerce').astype('Int64')

            # Ensure 'Player Name' is string type
            if 'Name' in df.columns:
                df['Player Name'] = df['Name']

            if 'Batting Type' in df.columns:
                df['Batting Type'] = df['Batting Type'].str.upper()
            if 'Pitching Type' in df.columns:
                df['Pitching Type'] = df['Pitching Type'].str.upper()
                df['Pitching Type'] = df['Pitching Type'].replace({'FB': 'FP', 'NTH': 'NT'})
            
            if 'Pitching Bonus' in df.columns and 'Pitching Type' in df.columns:
                df['Pitching Bonus'] = df['Pitching Bonus'].astype(str).str.upper()
                # Combine Pitching Type and Pitching Bonus
                df['Pitching Type'] = df.apply(
                    lambda row: f"{row['Pitching Type']}-{row['Pitching Bonus']}" if pd.notna(row['Pitching Bonus']) and row['Pitching Bonus'] != '' and row['Pitching Bonus'] != 'NAN' else row['Pitching Type'],
                    axis=1
                )
            player_type_data[season] = df

    return player_type_data

if __name__ == '__main__':
    # Example usage:
    try:
        import pandas
    except ImportError:
        print("The 'pandas' library is not installed. Please install it using 'pip install pandas'")
        sys.exit(1)
    else:
        all_data, _, _ = load_all_seasons()
        if all_data:
            print(f"\nSuccessfully loaded data for {len(all_data)} seasons.")
            # For example, print the first 5 rows of Season 5's data
            if 'S5' in all_data:
                print("\nFirst 5 rows of Season 5 data:")
                print(all_data['S5'].head())
