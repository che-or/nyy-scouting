from data_loader import load_all_seasons, load_player_types
from gamelog_corrections import apply_gamelog_corrections
import pandas as pd
import sys
import json
import os
import re
from collections import defaultdict

def _get_pitch_histogram_data(pitch_series, bin_size):
    pitch_series = pitch_series.dropna().astype(int)
    if pitch_series.empty: return []
    pitches = pitch_series.apply(lambda p: 0 if p == 1000 else p)
    bin_ids = pitches // bin_size
    histogram_data = bin_ids.value_counts()
    num_bins = (1000 + bin_size - 1) // bin_size
    all_bin_ids = range(num_bins)
    histogram_data = histogram_data.reindex(all_bin_ids, fill_value=0).sort_index()
    
    output = []
    for bin_id, count in histogram_data.items():
        lower_bound = bin_id * bin_size
        upper_bound = lower_bound + bin_size - 1
        if lower_bound == 0: lower_bound = 1
        label = f"{lower_bound}-{upper_bound}"
        output.append({'label': label, 'count': int(count)})
    return output

def get_scouting_report_data(player_id, pitcher_df, bin_size=100):
    if pitcher_df.empty: return None
    pitcher_df = pitcher_df.copy()
    pitcher_df['Pitch'] = pd.to_numeric(pitcher_df['Pitch'], errors='coerce')
    pitcher_df['Season_num'] = pitcher_df['Season'].str.replace('S', '').astype(int)
    pitcher_df.sort_values(by=['Season_num', 'Session', 'Inning'], inplace=True)
    
    valid_pitches = pitcher_df['Pitch'].dropna()
    top_5_pitches = valid_pitches.value_counts().nlargest(5)
    
    # Tendencies
    pitches = pitcher_df['Pitch'].to_numpy()
    repeat_count = (pitches[:-1] == pitches[1:]).sum()
    total_opportunities = len(pitches) - 1
    repeat_percentage = (repeat_count / total_opportunities) * 100 if total_opportunities > 0 else 0
    has_tripled_up = ((pitches[:-2] == pitches[1:-1]) & (pitches[1:-1] == pitches[2:])).any() if len(pitches) > 2 else False
    swing = pd.to_numeric(pitcher_df['Swing'], errors='coerce')
    diff = pd.to_numeric(pitcher_df['Diff'], errors='coerce')
    swing_match_rate = (pitcher_df['Pitch'] == swing.shift(1)).mean() * 100
    diff_match_rate = (pitcher_df['Pitch'] == diff.shift(1)).mean() * 100
    meme_numbers = {69, 420, 666, 327, 880}
    meme_percentage = pitcher_df['Pitch'].isin(meme_numbers).sum() / len(pitcher_df) * 100 if len(pitcher_df) > 0 else 0

    # Histograms
    histograms = {
        "overall": _get_pitch_histogram_data(pitcher_df['Pitch'], bin_size),
        "first_of_game": _get_pitch_histogram_data(pitcher_df.groupby(['Season', 'Game ID']).first()['Pitch'], bin_size),
        "first_of_inning": _get_pitch_histogram_data(pitcher_df.groupby(['Season', 'Game ID', 'Inning']).first()['Pitch'], bin_size),
        "risp": _get_pitch_histogram_data(pitcher_df[pd.to_numeric(pitcher_df['OBC'], errors='coerce').fillna(0) > 1]['Pitch'], bin_size)
    }

    # Conditional Histograms
    pitcher_df['pitch_norm'] = pitcher_df['Pitch'].apply(lambda x: 0 if x == 1000 else x)
    pitcher_df['previous_pitch'] = pitcher_df.groupby(['Season', 'Game ID'])['pitch_norm'].shift(1)
    
    conditional_histograms = {}
    for i in range(10):
        lower_bound = i * 100
        upper_bound = (i + 1) * 100
        
        filtered_df = pitcher_df[(pitcher_df['previous_pitch'] >= lower_bound) & (pitcher_df['previous_pitch'] < upper_bound)]
        
        if not filtered_df.empty:
            hist_data = _get_pitch_histogram_data(filtered_df['Pitch'], bin_size)
            key = f'after_{i}00s'
            if hist_data:
                conditional_histograms[key] = hist_data

    # By Season Histograms
    season_histograms = {}
    for season, season_df in pitcher_df.groupby('Season'):
        hist_data = _get_pitch_histogram_data(season_df['Pitch'], bin_size)
        if hist_data:
            season_histograms[season] = hist_data

    # Recent Game Info
    recent_game_info = {}
    if not pitcher_df.empty:
        last_game_row = pitcher_df.iloc[-1]
        last_game_season = last_game_row['Season']
        last_game_id = last_game_row['Game ID']
        
        last_game_df = pitcher_df[(pitcher_df['Season'] == last_game_season) & (pitcher_df['Game ID'] == last_game_id)]
        
        if not last_game_df.empty:
            last_game_details = last_game_df.iloc[0]
            opposing_teams = last_game_df['Batter Team'].unique()
            opposing_team = opposing_teams[0] if len(opposing_teams) > 0 else ''

            recent_game_info = {
                'pitcher_team': last_game_details['Pitcher Team'],
                'season': last_game_details['Season'],
                'session': int(last_game_details['Session']),
                'opponent': opposing_team,
                'pitches': last_game_df['Pitch'].dropna().astype(int).tolist()
            }

    return {
        "top_5_pitches": {int(k): int(v) for k, v in top_5_pitches.to_dict().items()},
        "histograms": histograms,
        "tendencies": {
            "repeat_percentage": round(repeat_percentage, 2),
            "has_tripled_up": bool(has_tripled_up),
            "swing_match_rate": round(swing_match_rate, 2),
            "diff_match_rate": round(diff_match_rate, 2),
            "meme_percentage": round(meme_percentage, 2)
        },
        "conditional_histograms": conditional_histograms,
        "season_histograms": season_histograms,
        "recent_game_info": recent_game_info
    }

def main():
    print("Loading all season data... (this may take a moment)")
    all_season_data, most_recent_season, force_recalc_seasons = load_all_seasons()
    if not all_season_data: return

    print("Loading player type data...")
    player_type_data = load_player_types(force_seasons=force_recalc_seasons)
    combined_df = pd.concat([df.assign(Season=season) for season, df in all_season_data.items() if not df.empty], ignore_index=True)

    print("Processing player info data...")
    player_info = {}
    if player_type_data:
        # Sort by season number to ensure correctness
        sorted_seasons = sorted(player_type_data.keys(), key=lambda s: int(s.replace('S', '')))
        for season in sorted_seasons:
            df = player_type_data[season]
            season_num = int(season.replace('S', ''))
            
            # Ensure all required columns exist, fill with None if not
            required_cols = ['Player ID', 'Primary Position', 'Batting Type', 'Pitching Type', 'Handedness']
            for col in required_cols:
                if col not in df.columns:
                    df[col] = None

            if 'Primary Position' in df.columns:
                # This rule applies to all seasons
                df.loc[~df['Primary Position'].isin(['P', 'PH']), 'Pitching Type'] = 'POS'
                
                # This rule only applies to S6 and later
                if season_num >= 6:
                    df.loc[df['Primary Position'] == 'P', 'Batting Type'] = 'P'

            df = df[required_cols].copy()
            df.rename(columns={'Player ID': 'player_id', 'Primary Position': 'primary_position', 'Batting Type': 'batting_type', 'Pitching Type': 'pitching_type', 'Handedness': 'handedness'}, inplace=True)
            df['player_id'] = pd.to_numeric(df['player_id'], errors='coerce')
            df.dropna(subset=['player_id'], inplace=True)
            df['player_id'] = df['player_id'].astype(int)
            
            df.drop_duplicates(subset=['player_id'], keep='first', inplace=True)
            
            df.set_index('player_id', inplace=True)
            df = df.where(pd.notnull(df), None)
            
            new_data = df.to_dict('index')
            for pid, data in new_data.items():
                if pid not in player_info:
                    player_info[pid] = {}
                for key, value in data.items():
                    if value is not None:
                        player_info[pid][key] = value

    print("Reconciling player IDs across seasons...")
    hitters_with_ids = combined_df[combined_df['Hitter ID'].notna()][['Hitter ID', 'Hitter', 'Season']].rename(columns={'Hitter ID': 'Player ID', 'Hitter': 'Player Name'})
    pitchers_with_ids = combined_df[combined_df['Pitcher ID'].notna()][['Pitcher ID', 'Pitcher', 'Season']].rename(columns={'Pitcher ID': 'Player ID', 'Pitcher': 'Player Name'})
    players_with_ids = pd.concat([hitters_with_ids, pitchers_with_ids]).drop_duplicates()
    players_with_ids['Player ID'] = players_with_ids['Player ID'].astype(int)
    
    name_to_id_season_map = defaultdict(lambda: defaultdict(set))
    for _, row in players_with_ids.iterrows():
        name_to_id_season_map[row['Player Name']][row['Player ID']].add(row['Season'])

    def find_adjacent_id(player_name, season_str):
        if player_name in name_to_id_season_map:
            season_num = int(season_str.replace('S', ''))
            for s_offset in [0, 1, -1]:
                adj_season_num = season_num + s_offset
                for pid, seasons in name_to_id_season_map[player_name].items():
                    if f"S{adj_season_num}" in seasons:
                        return pid
        return None

    for role in ['Hitter', 'Pitcher']:
        id_col, name_col = f'{role} ID', role
        missing_mask = combined_df[id_col].isna()
        if missing_mask.any():
            inferred_ids = combined_df[missing_mask].apply(
                lambda row: find_adjacent_id(row[name_col], row['Season']), axis=1
            )
            if not inferred_ids.empty:
                combined_df[id_col] = combined_df[id_col].astype('object')
                combined_df.loc[inferred_ids.index, id_col] = inferred_ids

    global_temp_id_counter = -1
    player_name_to_temp_id = {}

    def get_or_assign_temp_id(player_name):
        nonlocal global_temp_id_counter
        if player_name not in player_name_to_temp_id:
            player_name_to_temp_id[player_name] = global_temp_id_counter
            global_temp_id_counter -= 1
        return player_name_to_temp_id[player_name]

    no_id_mask = combined_df['Pitcher ID'].isna()
    if no_id_mask.any():
        combined_df.loc[no_id_mask, 'Pitcher ID'] = combined_df.loc[no_id_mask, 'Pitcher'].apply(get_or_assign_temp_id)

    no_id_mask_hitter = combined_df['Hitter ID'].isna()
    if no_id_mask_hitter.any():
        combined_df.loc[no_id_mask_hitter, 'Hitter ID'] = combined_df.loc[no_id_mask_hitter, 'Hitter'].apply(get_or_assign_temp_id)

    print("Applying manual gamelog corrections...")
    combined_df = combined_df.groupby(['Season', 'Game ID']).apply(
        lambda g: apply_gamelog_corrections(g, g.name), include_groups=False
    ).reset_index()
    print("Gamelog corrections applied.")

    all_players = pd.concat([
        combined_df[['Hitter ID', 'Hitter', 'Season', 'Session', 'Batter Team']].rename(columns={'Hitter ID': 'Player ID', 'Hitter': 'Player Name', 'Batter Team': 'Team'})
        ,
        combined_df[['Pitcher ID', 'Pitcher', 'Season', 'Session', 'Pitcher Team']].rename(columns={'Pitcher ID': 'Player ID', 'Pitcher': 'Player Name', 'Pitcher Team': 'Team'})
    ])
    all_players.dropna(subset=['Player ID', 'Player Name'], inplace=True)
    all_players['Player ID'] = all_players['Player ID'].astype(int)
    all_players['Season_num'] = all_players['Season'].str.replace('S', '').astype(int)
    all_players.sort_values(by=['Season_num', 'Session'], ascending=[False, False], inplace=True)
    
    player_names = all_players.groupby('Player ID')['Player Name'].apply(lambda x: list(dict.fromkeys(x))).to_dict()

    player_id_map = {}
    IMPORT_ERROR_STRING = "IMPORT ERROR"

    for player_id, names_list in player_names.items():
        if player_id == 0: continue
        if not names_list: continue

        valid_names = [name for name in names_list if name != IMPORT_ERROR_STRING]
        
        current_name = IMPORT_ERROR_STRING
        former_names = []

        if valid_names:
            current_name = valid_names[0]
            former_names = list(dict.fromkeys(valid_names[1:]))
        else:
            pass

        player_id_map[int(player_id)] = {
            'currentName': current_name,
            'formerNames': former_names
        }
    
    # Add most recent team to player info
    last_appearance = all_players.loc[all_players.groupby('Player ID')['Season_num'].idxmax()]
    for _, row in last_appearance.iterrows():
        pid = row['Player ID']
        if pid in player_info:
            player_info[pid]['last_team'] = row['Team']
            player_info[pid]['last_season'] = row['Season']

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'data')
    if not os.path.exists(output_dir): os.makedirs(output_dir)

    # Save player info
    with open(os.path.join(output_dir, 'player_info.json'), 'w') as f:
        json.dump(player_info, f, indent=4)
    print(f"Player info saved to {os.path.join(output_dir, 'player_info.json')}")

    # Save player ID map
    with open(os.path.join(output_dir, 'player_id_map.json'), 'w') as f:
        json.dump(player_id_map, f, indent=4)
    print(f"Player ID map saved to {os.path.join(output_dir, 'player_id_map.json')}")

    print("Generating scouting reports...")
    scouting_reports = {}
    all_pitcher_ids = combined_df['Pitcher ID'].unique()
    for pitcher_id in all_pitcher_ids:
        if pitcher_id <= 0: continue
        pitcher_df = combined_df[combined_df['Pitcher ID'] == pitcher_id]
        report = get_scouting_report_data(pitcher_id, pitcher_df)
        if report:
            scouting_reports[int(pitcher_id)] = report
    
    output_path = os.path.join(output_dir, 'scouting_reports.json')
    with open(output_path, 'w') as f:
        json.dump(scouting_reports, f)
    print(f"Scouting reports saved to {output_path}")

    print("Done!")

if __name__ == "__main__":
    main()
