from data_loader import load_all_seasons, load_player_types
from game_processing import get_pitching_decisions
from gamelog_corrections import apply_gamelog_corrections
from player_data_corrections import apply_postprocessing_corrections
import pandas as pd
import sys
import json
import os
import re
from collections import defaultdict




def _simulate_play_for_tracking(play, current_runners, outs):
    runs_scored = []
    runners = {k: v.copy() if v else None for k, v in current_runners.items()} # Deep copy
    batter = {'id': play['Hitter ID'], 'is_manfred': False}
    result = play['Exact Result'] if pd.notna(play['Exact Result']) else play['Old Result']
    advancement_bonus = 1 if outs == 2 and result in ['1B', '2B'] else 0

    # --- SIMULATE PLAY OUTCOME ---
    if result == 'HR':
        if runners[3]: runs_scored.append(runners[3])
        if runners[2]: runs_scored.append(runners[2])
        if runners[1]: runs_scored.append(runners[1])
        runs_scored.append(batter)
        runners = {1: None, 2: None, 3: None}
    elif result == '3B':
        if runners[3]: runs_scored.append(runners[3])
        if runners[2]: runs_scored.append(runners[2])
        if runners[1]: runs_scored.append(runners[1])
        runners = {1: None, 2: None, 3: batter}
    elif result == '2B':
        if runners[3]: runs_scored.append(runners[3])
        if runners[2]: runs_scored.append(runners[2])
        new_runners = {1: None, 2: batter, 3: None}
        if runners[1]: new_runners[3] = runners[1]
        runners = new_runners
    elif result in ['1B', 'BUNT 1B', 'Bunt 1B']:
        if advancement_bonus > 0 and result == '1B':
            if runners[3]: runs_scored.append(runners[3])
            if runners[2]: runs_scored.append(runners[2])
            if runners[1]: runners[3] = runners[1]
            runners = {1: batter, 2: None, 3: runners.get(1)}
        else:
            if runners[3]: runs_scored.append(runners[3])
            new_runners = {1: batter, 2: None, 3: None}
            if runners[2]: new_runners[3] = runners[2]
            if runners[1]: new_runners[2] = runners[1]
            runners = new_runners
    elif result in ['BB', 'IBB', 'Auto BB', 'AUTO BB']:
        if runners[1] and runners[2] and runners[3]: runs_scored.append(runners[3])
        new_runners = runners.copy()
        if runners[1] and runners[2]: new_runners[3] = runners[2]
        if runners[1]: new_runners[2] = runners[1]
        new_runners[1] = batter
        runners = new_runners
    # Add other out results here...

    return runs_scored, runners

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

def calculate_ops_plus_for_row(row, league_stats_by_season):
    if row['PA'] == 0:
        return pd.NA

    if 'Season' in row.index:
        season_name = row['Season']
    else:
        season_name = f"S{row.name}"

    season_stats = league_stats_by_season.get(season_name)
    if not season_stats or season_stats['lg_nOBP'] == 0 or season_stats['lg_nSLG'] == 0:
        return 100

    player_nobp = row['nOBP']
    player_nslg = row['nSLG']

    if pd.isna(player_nobp) or pd.isna(player_nslg):
        return pd.NA

    ops_plus = 100 * ((player_nobp / season_stats['lg_nOBP']) + (player_nslg / season_stats['lg_nSLG']) - 1)

    if pd.isna(ops_plus):
        return pd.NA

    return int(round(ops_plus))

def format_ip(ip_float):
    whole_innings = int(ip_float)
    outs = round((ip_float - whole_innings) * 3)
    if outs == 3:
        whole_innings += 1
        outs = 0
    return f"{whole_innings}.{outs}"

def calculate_hitting_stats(df, season=None):
    if df.empty: return None

    if season is None:
        season = df.name
    use_old_results = season in ['S2', 'S3']

    if use_old_results:
        result_col = 'Old Result'
        hits = {'1B', '2B', '3B', 'HR'}
        walks = {'BB', 'IBB', 'Auto BB'}
        strikeouts = {'K', 'Auto K'}
        stolen_bases = {'SB'}
        caught_stealing = {'CS'}
        pa_events = hits | walks | strikeouts | {'FO', 'PO', 'LGO', 'RGO', 'LO', 'DP', 'TP', 'Sac', 'Bunt'}
    else:
        result_col = 'Exact Result'
        hits = {'1B', '2B', '3B', 'HR', 'BUNT 1B', 'Bunt 1B'}
        walks = {'BB', 'IBB', 'Auto BB', 'AUTO BB'}
        strikeouts = {'K', 'Auto K', 'Bunt K', 'AUTO K', 'BUNT K'}
        stolen_bases = {'STEAL 2B', 'STEAL 3B', 'Steal 2B', 'Steal 3B', 'MSTEAL 3B', 'MSteal 3B'}
        caught_stealing = {'CS 2B', 'CS 3B', 'CS Home', 'CMS 3B', 'CMS Home'}
        pa_events = hits | walks | strikeouts | {'FO', 'PO', 'LGO', 'RGO', 'LO', 'BUNT DP', 'Bunt DP', 'BUNT GO', 'Bunt GO', 'BUNT Sac', 'Bunt Sac'}

    if use_old_results:
        diff_events = pa_events | stolen_bases | caught_stealing
        diff_df = df[df[result_col].isin(diff_events)]
        pa_df = df[df[result_col].isin(pa_events)]
    else:
        diff_events_exact = pa_events | stolen_bases | caught_stealing
        exact_diff_df = df[df['Exact Result'].isin(diff_events_exact)]
        old_diff_df = df[df['Old Result'].isin(['DP', 'TP'])]
        diff_df = pd.concat([exact_diff_df, old_diff_df]).drop_duplicates()

        exact_pa_df = df[df['Exact Result'].isin(pa_events)]
        old_pa_df = df[df['Old Result'].isin(['DP', 'TP'])]
        pa_df = pd.concat([exact_pa_df, old_pa_df]).drop_duplicates()

    numeric_diff = pd.to_numeric(diff_df['Diff'], errors='coerce')
    avg_diff = numeric_diff.mean()

    num_sb = df[df[result_col].isin(stolen_bases)].shape[0]
    num_cs = df[df[result_col].isin(caught_stealing)].shape[0]

    pa = len(pa_df)

    re24_events = pa_events | stolen_bases | caught_stealing
    re24_df = df[df[result_col].isin(re24_events)]
    re24 = re24_df['RE24'].sum() if 'RE24' in re24_df.columns else 0
    wpa = re24_df['Batter WPA'].sum() if 'Batter WPA' in re24_df.columns else 0

    if pa == 0:
        runs_scored = df['Run'].sum()
        sb_pct = num_sb / (num_sb + num_cs) if (num_sb + num_cs) > 0 else pd.NA
        return pd.Series({'G': df['Session'].nunique(), 'PA': 0, 'AB': 0, 'H': 0, 'R': runs_scored, 'RBI': 0, '1B': 0, '2B': 0, '3B': 0, 'HR': 0, 'TB': 0, 'BB': 0, 'IBB': 0, 'Auto K': 0, 'K': 0, 'SB': num_sb, 'CS': num_cs, 'SH': 0, 'SF': 0, 'GIDP': 0, 'RGO': 0, 'LGO': 0, 'FO': 0, 'PO': 0, 'LO': 0, 'AVG': pd.NA, 'OBP': pd.NA, 'SLG': pd.NA, 'OPS': pd.NA, 'Avg Diff': avg_diff, 'RE24': re24, 'WPA': wpa, 'ISO': pd.NA, 'BABIP': pd.NA, 'SB%': sb_pct, 'HR%': pd.NA, 'SO%': pd.NA, 'BB%': pd.NA, 'GB%': pd.NA, 'FB%': pd.NA, 'GB/FB': pd.NA, 'GB_outs': 0, 'FB_outs': 0, 'nOBP': pd.NA, 'nSLG': pd.NA})

    games_played = df['Session'].nunique()
    num_walks = pa_df[pa_df[result_col].isin(walks)].shape[0]
    num_ibb = pa_df[pa_df[result_col] == 'IBB'].shape[0]
    
    num_gidp = pa_df[(pa_df['Old Result'].isin(['DP', 'TP'])) | (pa_df['Exact Result'] == 'BUNT DP')].shape[0]

    if use_old_results:
        num_sh = pa_df[pa_df['Old Result'] == 'Bunt'].shape[0]
        num_sf = pa_df[pa_df['Old Result'] == 'Sac'].shape[0]
    else:
        num_sh = pa_df[pa_df['Exact Result'].isin(['BUNT Sac', 'Bunt Sac'])].shape[0]
        num_sf = pa_df[(pa_df['Exact Result'] == 'FO') & (pd.to_numeric(pa_df['RBI'], errors='coerce').fillna(0) > 0)].shape[0]

    num_sacrifices = num_sh + num_sf
    
    ab = pa - num_walks - num_sacrifices
    num_hits = pa_df[pa_df[result_col].isin(hits)].shape[0]
    num_doubles = pa_df[pa_df[result_col] == '2B'].shape[0]
    num_triples = pa_df[pa_df[result_col] == '3B'].shape[0]
    num_hr = pa_df[pa_df[result_col] == 'HR'].shape[0]
    num_singles = pa_df[pa_df[result_col] == '1B'].shape[0]
    if not use_old_results:
        num_singles += pa_df[pa_df[result_col] == 'BUNT 1B'].shape[0]

    num_tb = num_singles + (num_doubles * 2) + (num_triples * 3) + (num_hr * 4)
    num_strikeouts = pa_df[pa_df[result_col].isin(strikeouts)].shape[0]
    num_auto_k = pa_df[pa_df[result_col].isin(['Auto K', 'AUTO K'])].shape[0]
    num_rgo = pa_df[pa_df[result_col] == 'RGO'].shape[0]
    num_lgo = pa_df[pa_df[result_col] == 'LGO'].shape[0]
    num_fo = pa_df[pa_df[result_col] == 'FO'].shape[0]
    num_po = pa_df[pa_df[result_col] == 'PO'].shape[0]
    num_lo = pa_df[pa_df[result_col] == 'LO'].shape[0]

    runs_scored = df['Run'].sum()
    rbi = df['RBI'].sum()

    avg = num_hits / ab if ab > 0 else pd.NA
    obp = (num_hits + num_walks) / (ab + num_walks + num_sf) if (ab + num_walks + num_sf) > 0 else pd.NA
    slg = num_tb / ab if ab > 0 else pd.NA
    ops = obp + slg if pd.notna(obp) and pd.notna(slg) else pd.NA
    iso = slg - avg if pd.notna(slg) and pd.notna(avg) else pd.NA
    babip = (num_hits - num_hr) / (ab - num_strikeouts - num_hr + num_sf) if (ab - num_strikeouts - num_hr + num_sf) > 0 else pd.NA
    sb_pct = num_sb / (num_sb + num_cs) if (num_sb + num_cs) > 0 else pd.NA
    hr_pct = num_hr / pa if pa > 0 else pd.NA
    so_pct = num_strikeouts / pa if pa > 0 else pd.NA
    bb_pct = num_walks / pa if pa > 0 else pd.NA

    num_gb_outs = num_rgo + num_lgo + num_gidp
    num_fb_outs = num_fo + num_po + num_lo + num_sf
    total_bip_outs = num_gb_outs + num_fb_outs

    gb_pct = num_gb_outs / total_bip_outs if total_bip_outs > 0 else pd.NA
    fb_pct = num_fb_outs / total_bip_outs if total_bip_outs > 0 else pd.NA
    gb_fb_ratio = num_gb_outs / num_fb_outs if num_fb_outs > 0 else pd.NA

    # Initialize all neutral component variables to pd.NA
    n_pa_val = pd.NA
    n_ab_val = pd.NA
    n_num_hits_val = pd.NA
    n_num_walks_val = pd.NA
    n_num_sf_val = pd.NA
    n_num_sh_val = pd.NA
    n_num_tb_val = pd.NA

    nOBP = obp
    nSLG = slg

    use_neutral_results = season not in ['S1', 'S2']
    if use_neutral_results:
        neutral_result_col = 'Result at Neutral'
        neutral_df = df[df[neutral_result_col].notna()]
        
        if not neutral_df.empty:
            # Define event sets for neutral results, combining old and new possibilities
            n_hits = {'1B', '2B', '3B', 'HR', 'BUNT 1B', 'Bunt 1B'}
            n_walks = {'BB', 'IBB', 'Auto BB', 'AUTO BB'}
            n_strikeouts = {'K', 'Auto K', 'Bunt K', 'AUTO K', 'BUNT K'}
            n_pa_events = n_hits | n_walks | n_strikeouts | {'FO', 'PO', 'LGO', 'RGO', 'LO', 'DP', 'TP', 'Sac', 'Bunt', 'BUNT DP', 'Bunt DP', 'BUNT GO', 'Bunt GO', 'BUNT Sac', 'Bunt Sac'}

            n_pa_df = neutral_df[neutral_df[neutral_result_col].isin(n_pa_events)]
            n_pa_current = len(n_pa_df)
            n_pa_val = n_pa_current

            if n_pa_current > 0:
                n_num_walks_current = n_pa_df[n_pa_df[neutral_result_col].isin(n_walks)].shape[0]
                n_num_hits_current = n_pa_df[n_pa_df[neutral_result_col].isin(n_hits)].shape[0]

                n_num_sf_current = n_pa_df[n_pa_df[neutral_result_col] == 'Sac'].shape[0]
                n_num_sh_current = n_pa_df[n_pa_df[neutral_result_col].isin(['Bunt', 'BUNT Sac', 'Bunt Sac'])].shape[0]
                n_num_sacrifices_current = n_num_sh_current + n_num_sf_current
                
                n_ab_current = n_pa_current - n_num_walks_current - n_num_sacrifices_current
                
                n_ab_val = n_ab_current
                n_num_hits_val = n_num_hits_current
                n_num_walks_val = n_num_walks_current
                n_num_sf_val = n_num_sf_current
                n_num_sh_val = n_num_sh_current

                if (n_ab_current + n_num_walks_current + n_num_sf_current) > 0:
                    calculated_nOBP = (n_num_hits_current + n_num_walks_current) / (n_ab_current + n_num_walks_current + n_num_sf_current)
                    if not pd.isna(calculated_nOBP):
                        nOBP = calculated_nOBP
                
                if n_ab_current > 0:
                    n_num_doubles = n_pa_df[n_pa_df[neutral_result_col] == '2B'].shape[0]
                    n_num_triples = n_pa_df[n_pa_df[neutral_result_col] == '3B'].shape[0]
                    n_num_hr = n_pa_df[n_pa_df[neutral_result_col] == 'HR'].shape[0]
                    n_num_singles = n_pa_df[n_pa_df[neutral_result_col].isin(['1B', 'BUNT 1B', 'Bunt 1B'])].shape[0]
                    n_num_tb_current = n_num_singles + (n_num_doubles * 2) + (n_num_triples * 3) + (n_num_hr * 4)
                    n_num_tb_val = n_num_tb_current
                    
                    calculated_nSLG = n_num_tb_current / n_ab_current
                    if not pd.isna(calculated_nSLG):
                        nSLG = calculated_nSLG

    batting_type = df['Hitter Batting Type'].iloc[0] if 'Hitter Batting Type' in df.columns and not df['Hitter Batting Type'].dropna().empty else None

    series_data = {
        'G': games_played, 'PA': pa, 'AB': ab, 'H': num_hits, 'R': runs_scored, '1B': num_singles, '2B': num_doubles, '3B': num_triples, 'HR': num_hr, 'TB': num_tb, 'RBI': rbi,
        'BB': num_walks, 'IBB': num_ibb, 'K': num_strikeouts, 'Auto K': num_auto_k, 'SB': num_sb, 'CS': num_cs, 'SH': num_sh, 'SF': num_sf, 'GIDP': num_gidp,
        'RGO': num_rgo, 'LGO': num_lgo, 'FO': num_fo, 'PO': num_po, 'LO': num_lo,
        'AVG': avg, 'OBP': obp, 'SLG': slg, 'OPS': ops, 'ISO': iso, 'BABIP': babip,
        'SB%': sb_pct, 'HR%': hr_pct, 'SO%': so_pct, 'BB%': bb_pct,
        'GB%': gb_pct, 'FB%': fb_pct, 'GB/FB': gb_fb_ratio,
        'Avg Diff': avg_diff,
        'nOBP': nOBP, 'nSLG': nSLG, 'RE24': re24, 'WPA': wpa,
        'GB_outs': num_gb_outs, 'FB_outs': num_fb_outs,
        'Type': batting_type
    }

    if pd.notna(n_pa_val): # Only update if neutral stats were actually calculated
        series_data.update({
            'nPA': n_pa_val,
            'nAB': n_ab_val,
            'nH': n_num_hits_val,
            'nTB': n_num_tb_val,
            'nBB': n_num_walks_val,
            'nSF': n_num_sf_val,
            'nSH': n_num_sh_val,
        })

    return pd.Series(series_data)

def calculate_pitching_stats(df, season=None):
    if df.empty: return None

    if season is None:
        season = df.name
    use_old_results = season in ['S2', 'S3']

    if use_old_results:
        result_col = 'Old Result'
        hits_allowed = {'1B', '2B', '3B', 'HR'}
        walks_allowed = {'BB', 'IBB', 'Auto BB'}
        ibb_events = {'IBB'}
        strikeouts = {'K', 'Auto K'}
        hr_allowed = {'HR'}
        single_out_bip = {'FO', 'LGO', 'PO', 'RGO', 'Bunt', 'LO'}
        caught_stealing = {'CS'}
        stolen_bases = {'SB'}
    else:
        result_col = 'Exact Result'
        hits_allowed = {'1B', '2B', '3B', 'HR', 'BUNT 1B', 'Bunt 1B'}
        walks_allowed = {'BB', 'IBB', 'Auto BB', 'AUTO BB'}
        ibb_events = {'IBB'}
        strikeouts = {'K', 'Auto K', 'Bunt K', 'AUTO K', 'BUNT K'}
        hr_allowed = {'HR'}
        single_out_bip = {'FO', 'LGO', 'PO', 'RGO', 'LO', 'BUNT GO', 'Bunt GO', 'BUNT Sac', 'Bunt Sac'}
        caught_stealing = {'CS 2B', 'CS 3B', 'CS Home', 'CMS 3B', 'CMS Home'}
        stolen_bases = {'STEAL 2B', 'STEAL 3B', 'Steal 2B', 'Steal 3B', 'MSTEAL 3B', 'MSteal 3B'}

    num_sb_allowed = df[df[result_col].isin(stolen_bases)].shape[0]
    num_cs_against = df[df[result_col].isin(caught_stealing)].shape[0]
    sb_pct_against = num_sb_allowed / (num_sb_allowed + num_cs_against) if (num_sb_allowed + num_cs_against) > 0 else pd.NA

    if use_old_results:
        pitching_pa_events = hits_allowed | walks_allowed | strikeouts | single_out_bip | {'DP', 'TP', 'Sac'}
        diff_events = pitching_pa_events | stolen_bases | caught_stealing
        diff_df = df[df[result_col].isin(diff_events)]
    else:
        pa_events_exact = hits_allowed | walks_allowed | strikeouts | single_out_bip | {'BUNT DP'}
        diff_events_exact = pa_events_exact | stolen_bases | caught_stealing
        
        exact_df = df[df['Exact Result'].isin(diff_events_exact)]
        old_df = df[df['Old Result'].isin(['DP', 'TP'])]
        
        diff_df = pd.concat([exact_df, old_df]).drop_duplicates()

    numeric_diff = pd.to_numeric(diff_df['Diff'], errors='coerce')
    avg_diff = numeric_diff.mean()

    if use_old_results:
        pitching_pa_events = hits_allowed | walks_allowed | strikeouts | single_out_bip | {'DP', 'TP', 'Sac'}
        bf_df = df[df[result_col].isin(pitching_pa_events)]
        num_bf = bf_df.shape[0]
        re24_events = pitching_pa_events | stolen_bases | caught_stealing
        re24_df = df[df[result_col].isin(re24_events)]
    else:
        pa_events_exact = hits_allowed | walks_allowed | strikeouts | single_out_bip | {'BUNT DP'}
        exact_pa_df = df[df['Exact Result'].isin(pa_events_exact)]
        old_pa_df = df[df['Old Result'].isin(['DP', 'TP'])]
        bf_df = pd.concat([exact_pa_df, old_pa_df]).drop_duplicates()
        num_bf = bf_df.shape[0]
        re24_events_exact = pa_events_exact | stolen_bases | caught_stealing
        exact_re24_df = df[df['Exact Result'].isin(re24_events_exact)]
        re24_df = pd.concat([exact_re24_df, old_pa_df]).drop_duplicates()

    re24 = re24_df['RE24'].sum() if 'RE24' in re24_df.columns else 0
    wpa = re24_df['Pitcher WPA'].sum() if 'Pitcher WPA' in re24_df.columns else 0

    games_played = df['Session'].nunique()
    num_hits_allowed = bf_df[bf_df[result_col].isin(hits_allowed)].shape[0]
    num_walks_allowed = bf_df[bf_df[result_col].isin(walks_allowed)].shape[0]
    num_auto_bb_allowed = bf_df[bf_df[result_col].isin(['Auto BB', 'AUTO BB'])].shape[0]
    num_ibb = bf_df[bf_df[result_col].isin(ibb_events)].shape[0]
    num_strikeouts = bf_df[bf_df[result_col].isin(strikeouts)].shape[0]
    num_hr_allowed = bf_df[bf_df[result_col].isin(hr_allowed)].shape[0]

    dp_outs = df[df['Old Result'] == 'DP'].shape[0] * 2
    tp_outs = df[df['Old Result'] == 'TP'].shape[0] * 3

    non_dp_tp_df = df[~df['Old Result'].isin(['DP', 'TP'])]
    k_outs = non_dp_tp_df[non_dp_tp_df[result_col].isin(strikeouts)].shape[0]
    other_single_outs = non_dp_tp_df[non_dp_tp_df[result_col].isin(single_out_bip)].shape[0]
    cs_outs = non_dp_tp_df[non_dp_tp_df[result_col].isin(caught_stealing)].shape[0]

    total_outs = dp_outs + tp_outs + k_outs + other_single_outs + cs_outs
    ip = total_outs / 3

    runs_allowed = df['Run'].sum()
    unearned_runs = df['is_unearned'].sum() if 'is_unearned' in df.columns else 0
    earned_runs = runs_allowed - unearned_runs

    sac_events_df = bf_df[bf_df['Old Result'] == 'Sac']
    num_sf_allowed = sac_events_df[pd.to_numeric(sac_events_df['RBI'], errors='coerce').fillna(0) > 0].shape[0]
    num_sh_allowed = len(sac_events_df) - num_sf_allowed
    
    ab_against = num_bf - num_walks_allowed - num_sh_allowed - num_sf_allowed

    num_doubles_allowed = bf_df[bf_df[result_col] == '2B'].shape[0]
    num_triples_allowed = bf_df[bf_df[result_col] == '3B'].shape[0]
    num_singles_allowed = num_hits_allowed - num_doubles_allowed - num_triples_allowed - num_hr_allowed

    baa = num_hits_allowed / ab_against if ab_against > 0 else pd.NA
    obpa = (num_hits_allowed + num_walks_allowed) / num_bf if num_bf > 0 else pd.NA
    slga = (num_singles_allowed + 2*num_doubles_allowed + 3*num_triples_allowed + 4*num_hr_allowed) / ab_against if ab_against > 0 else pd.NA
    opsa = obpa + slga if pd.notna(obpa) and pd.notna(slga) else pd.NA

    babip_denom = ab_against - num_strikeouts - num_hr_allowed + num_sf_allowed
    babip_against = (num_hits_allowed - num_hr_allowed) / babip_denom if babip_denom > 0 else pd.NA

    hr_pct_against = num_hr_allowed / num_bf if num_bf > 0 else pd.NA
    k_pct_against = num_strikeouts / num_bf if num_bf > 0 else pd.NA
    bb_pct_against = num_walks_allowed / num_bf if num_bf > 0 else pd.NA

    fly_ball_events = {'FO', 'PO'}
    ground_ball_events = {'LGO', 'RGO', 'BUNT GO'}
    num_fb_outs_allowed = bf_df[bf_df[result_col].isin(fly_ball_events)].shape[0]
    num_gidp_allowed = bf_df[(bf_df['Old Result'].isin(['DP', 'TP'])) | (bf_df['Exact Result'] == 'BUNT DP')].shape[0]
    num_gb_outs_allowed = bf_df[bf_df[result_col].isin(ground_ball_events)].shape[0] + num_gidp_allowed
    
    total_fb_gb_allowed = num_fb_outs_allowed + num_gb_outs_allowed
    gb_pct_against = num_gb_outs_allowed / total_fb_gb_allowed if total_fb_gb_allowed > 0 else pd.NA
    fb_pct_against = num_fb_outs_allowed / total_fb_gb_allowed if total_fb_gb_allowed > 0 else pd.NA
    num_rgo_allowed = bf_df[bf_df[result_col] == 'RGO'].shape[0]
    num_lgo_allowed = bf_df[bf_df[result_col] == 'LGO'].shape[0]
    num_fo_allowed = bf_df[bf_df[result_col] == 'FO'].shape[0]
    num_po_allowed = bf_df[bf_df[result_col] == 'PO'].shape[0]
    num_lo_allowed = bf_df[bf_df[result_col] == 'LO'].shape[0]

    gb_fb_ratio_against = num_gb_outs_allowed / num_fb_outs_allowed if num_fb_outs_allowed > 0 else pd.NA

    h6 = (num_hits_allowed / ip) * 6 if ip > 0 else pd.NA
    hr6 = (num_hr_allowed / ip) * 6 if ip > 0 else pd.NA
    bb6 = (num_walks_allowed / ip) * 6 if ip > 0 else pd.NA
    k6 = (num_strikeouts / ip) * 6 if ip > 0 else pd.NA
    k_bb = num_strikeouts / num_walks_allowed if num_walks_allowed > 0 else pd.NA

    pitching_type = df['Pitcher Pitching Type'].iloc[0] if 'Pitcher Pitching Type' in df.columns and not df['Pitcher Pitching Type'].dropna().empty else None
    
    return pd.Series({
        'G': games_played, 'IP': ip, 'BF': num_bf, 'H': num_hits_allowed, 'R': runs_allowed, 'ER': earned_runs, 'BB': num_walks_allowed, 'IBB': num_ibb, 'Auto BB': num_auto_bb_allowed, 'K': num_strikeouts, 'HR': num_hr_allowed,
        '1B': num_singles_allowed, 'RGO': num_rgo_allowed, 'LGO': num_lgo_allowed, 'FO': num_fo_allowed, 'PO': num_po_allowed, 'LO': num_lo_allowed,
        'ERA': (earned_runs * 6) / ip if ip > 0 else pd.NA,
        'WHIP': (num_walks_allowed + num_hits_allowed) / ip if ip > 0 else pd.NA,
        'H/6': h6, 'HR/6': hr6, 'BB/6': bb6, 'K/6': k6, 'K/BB': k_bb,
        'BAA': baa, 'OBPA': obpa, 'SLGA': slga, 'OPSA': opsa, 'BABIP_A': babip_against,
        'HR%_A': hr_pct_against, 'K%_A': k_pct_against, 'BB%_A': bb_pct_against,
        'GB%_A': gb_pct_against, 'FB%_A': fb_pct_against, 'GB/FB_A': gb_fb_ratio_against,
        'Avg Diff': avg_diff,
        'RE24': re24,
        'WPA': wpa,
        'AB_A': ab_against, 'SF_A': num_sf_allowed, 'SH_A': num_sh_allowed,
        '2B_A': num_doubles_allowed, '3B_A': num_triples_allowed,
        'GB_outs_A': num_gb_outs_allowed, 'FB_outs_A': num_fb_outs_allowed,
        'SB_A': num_sb_allowed, 'CS_A': num_cs_against, 'SB%_A': sb_pct_against,
        'Type': pitching_type
    })

def calculate_team_hitting_stats(df, league_stats_for_season):
    sum_cols = ['G', 'PA', 'AB', 'H', 'R', '1B', '2B', '3B', 'HR', 'TB', 'RBI', 'BB', 'IBB', 'K', 'Auto K', 'SB', 'CS', 'SH', 'SF', 'GIDP', 'RGO', 'LGO', 'FO', 'PO', 'LO', 'RE24', 'WPA', 'WAR', 'GB_outs', 'FB_outs']
    neutral_cols = ['nPA', 'nAB', 'nH', 'nTB', 'nBB', 'nSF', 'nSH']
    
    # Ensure neutral columns exist and are numeric before summing
    for col in neutral_cols:
        if col not in df.columns:
            df[col] = 0
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df[neutral_cols] = df[neutral_cols].fillna(0)
    
    summed_stats = df[sum_cols + neutral_cols].sum()
    pa = summed_stats['PA']
    ab = summed_stats['AB']
    num_hits = summed_stats['H']
    num_walks = summed_stats['BB']
    num_sf = summed_stats['SF']
    num_tb = summed_stats['TB']
    num_hr = summed_stats['HR']
    num_strikeouts = summed_stats['K']
    num_sb = summed_stats['SB']
    num_cs = summed_stats['CS']
    num_rgo = summed_stats['RGO']
    num_lgo = summed_stats['LGO']
    num_gidp = summed_stats['GIDP']
    num_fo = summed_stats['FO']
    num_po = summed_stats['PO']
    num_lo = summed_stats['LO']
    avg = num_hits / ab if ab > 0 else 0
    obp = (num_hits + num_walks) / (ab + num_walks + num_sf) if (ab + num_walks + num_sf) > 0 else 0
    slg = num_tb / ab if ab > 0 else 0
    ops = obp + slg
    iso = slg - avg
    babip = (num_hits - num_hr) / (ab - num_strikeouts - num_hr + num_sf) if (ab - num_strikeouts - num_hr + num_sf) > 0 else 0
    sb_pct = num_sb / (num_sb + num_cs) if (num_sb + num_cs) > 0 else 0
    hr_pct = num_hr / pa if pa > 0 else 0
    so_pct = num_strikeouts / pa if pa > 0 else 0
    bb_pct = num_walks / pa if pa > 0 else 0
    num_gb_outs = num_rgo + num_lgo + num_gidp
    num_fb_outs = num_fo + num_po + num_lo + num_sf
    total_bip_outs = num_gb_outs + num_fb_outs
    gb_pct = num_gb_outs / total_bip_outs if total_bip_outs > 0 else 0
    fb_pct = num_fb_outs / total_bip_outs if total_bip_outs > 0 else 0
    gb_fb_ratio = num_gb_outs / num_fb_outs if num_fb_outs > 0 else 0

    # --- NEW: Calculate team nOBP and nSLG from summed neutral components ---
    team_nOBP = obp
    team_nSLG = slg

    if summed_stats['nPA'] > 0:
        n_ab = summed_stats['nAB']
        n_bb = summed_stats['nBB']
        n_sf = summed_stats['nSF']
        n_h = summed_stats['nH']
        n_tb = summed_stats['nTB']

        if (n_ab + n_bb + n_sf) > 0:
            team_nOBP = (n_h + n_bb) / (n_ab + n_bb + n_sf)
        if n_ab > 0:
            team_nSLG = n_tb / n_ab
    
    if league_stats_for_season and league_stats_for_season.get('lg_nOBP', 0) > 0 and league_stats_for_season.get('lg_nSLG', 0) > 0:
        ops_plus = 100 * ((team_nOBP / league_stats_for_season['lg_nOBP']) + (team_nSLG / league_stats_for_season['lg_nSLG']) - 1)
    else:
        ops_plus = 100
    ops_plus = round(ops_plus)

    df = df.copy()
    df['weight'] = df['PA'] + df['SB'] + df['CS']
    weighted_avg_diff = (df['Avg Diff'] * df['weight']).sum()
    total_weight = df['weight'].sum()
    avg_diff = weighted_avg_diff / total_weight if total_weight > 0 else 0

    team_stats = summed_stats.copy()
    team_stats['AVG'] = avg
    team_stats['OBP'] = obp
    team_stats['SLG'] = slg
    team_stats['OPS'] = ops
    team_stats['ISO'] = iso
    team_stats['BABIP'] = babip
    team_stats['SB%'] = sb_pct
    team_stats['HR%'] = hr_pct
    team_stats['SO%'] = so_pct
    team_stats['BB%'] = bb_pct
    team_stats['GB%'] = gb_pct
    team_stats['FB%'] = fb_pct
    team_stats['GB/FB'] = gb_fb_ratio
    team_stats['OPS+'] = ops_plus
    team_stats['Avg Diff'] = avg_diff
    team_stats['nOBP'] = team_nOBP
    team_stats['nSLG'] = team_nSLG
    return team_stats

def calculate_team_pitching_stats(df, league_n_era_for_season, team_n_era, fip_constant):
    summed_stats = df[['IP', 'BF', 'H', 'R', 'ER', 'BB', 'IBB', 'Auto BB', 'K', 'HR', 'W', 'L', 'SV', 'HLD', 'GS', 'GF', 'CG', 'SHO', 'RE24', 'WPA', 'WAR', 'AB_A', 'SF_A', 'SH_A', '1B', '2B_A', '3B_A', 'RGO', 'LGO', 'FO', 'PO', 'LO', 'GB_outs_A', 'FB_outs_A', 'SB_A', 'CS_A']].sum()
    summed_stats['G'] = df['GS'].sum()

    ip = summed_stats['IP']
    num_hits_allowed = summed_stats['H']
    num_walks_allowed = summed_stats['BB']
    earned_runs = summed_stats['ER']
    num_hr_allowed = summed_stats['HR']
    num_strikeouts = summed_stats['K']
    ab_against = summed_stats['AB_A']
    num_sf_allowed = summed_stats['SF_A']
    num_gb_outs_allowed = summed_stats['GB_outs_A']
    num_fb_outs_allowed = summed_stats['FB_outs_A']
    num_sb_allowed = summed_stats['SB_A']
    num_cs_against = summed_stats['CS_A']

    era = (earned_runs * 6) / ip if ip > 0 else 0
    whip = (num_walks_allowed + num_hits_allowed) / ip if ip > 0 else 0
    h6 = (num_hits_allowed / ip) * 6 if ip > 0 else 0
    hr6 = (num_hr_allowed / ip) * 6 if ip > 0 else 0
    bb6 = (num_walks_allowed / ip) * 6 if ip > 0 else 0
    k6 = (num_strikeouts / ip) * 6 if ip > 0 else 0
    k_bb = num_strikeouts / num_walks_allowed if num_walks_allowed > 0 else 0
    baa = num_hits_allowed / ab_against if ab_against > 0 else 0
    obpa = (num_hits_allowed + num_walks_allowed) / summed_stats['BF'] if summed_stats['BF'] > 0 else 0
    tb_allowed = summed_stats['1B'] + 2*summed_stats['2B_A'] + 3*summed_stats['3B_A'] + 4*summed_stats['HR']
    slga = tb_allowed / ab_against if ab_against > 0 else 0
    opsa = obpa + slga
    babip_denom = ab_against - num_strikeouts - num_hr_allowed + num_sf_allowed
    babip_against = (num_hits_allowed - num_hr_allowed) / babip_denom if babip_denom > 0 else 0
    hr_pct_against = num_hr_allowed / summed_stats['BF'] if summed_stats['BF'] > 0 else 0
    k_pct_against = num_strikeouts / summed_stats['BF'] if summed_stats['BF'] > 0 else 0
    bb_pct_against = num_walks_allowed / summed_stats['BF'] if summed_stats['BF'] > 0 else 0
    total_fb_gb_allowed = num_fb_outs_allowed + num_gb_outs_allowed
    gb_pct_against = num_gb_outs_allowed / total_fb_gb_allowed if total_fb_gb_allowed > 0 else 0
    fb_pct_against = num_fb_outs_allowed / total_fb_gb_allowed if total_fb_gb_allowed > 0 else 0
    gb_fb_ratio_against = num_gb_outs_allowed / num_fb_outs_allowed if num_fb_outs_allowed > 0 else 0
    sb_pct_against = num_sb_allowed / (num_sb_allowed + num_cs_against) if (num_sb_allowed + num_cs_against) > 0 else 0
    
    fip = ((13 * summed_stats['HR']) + (3 * summed_stats['BB']) - (2 * summed_stats['K'])) / ip + fip_constant if ip > 0 else 0

    if league_n_era_for_season > 0:
        era_minus = round(100 * (team_n_era / league_n_era_for_season))
    else:
        era_minus = 100

    df = df.copy()
    df['weight'] = df['BF'] + df['SB_A'] + df['CS_A']
    weighted_avg_diff = (df['Avg Diff'] * df['weight']).sum()
    total_weight = df['weight'].sum()
    avg_diff = weighted_avg_diff / total_weight if total_weight > 0 else 0

    team_stats = summed_stats.copy()
    team_stats['ERA'] = era
    team_stats['WHIP'] = whip
    team_stats['H/6'] = h6
    team_stats['HR/6'] = hr6
    team_stats['BB/6'] = bb6
    team_stats['K/6'] = k6
    team_stats['K/BB'] = k_bb
    team_stats['BAA'] = baa
    team_stats['OBPA'] = obpa
    team_stats['SLGA'] = slga
    team_stats['OPSA'] = opsa
    team_stats['BABIP_A'] = babip_against
    team_stats['HR%_A'] = hr_pct_against
    team_stats['K%_A'] = k_pct_against
    team_stats['BB%_A'] = bb_pct_against
    team_stats['GB%_A'] = gb_pct_against
    team_stats['FB%_A'] = fb_pct_against
    team_stats['GB/FB_A'] = gb_fb_ratio_against
    team_stats['SB%_A'] = sb_pct_against
    team_stats['Avg Diff'] = avg_diff
    team_stats['FIP'] = fip
    team_stats['ERA-'] = era_minus
    team_stats['W-L%'] = summed_stats['W'] / (summed_stats['W'] + summed_stats['L']) if (summed_stats['W'] + summed_stats['L']) > 0 else 0
    return team_stats

def calculate_career_hitting_stats(df, league_stats_by_season, include_type_column=True):
    sum_cols = ['G', 'PA', 'AB', 'H', 'R', '1B', '2B', '3B', 'HR', 'TB', 'RBI', 'BB', 'IBB', 'K', 'Auto K', 'SB', 'CS', 'SH', 'SF', 'GIDP', 'RGO', 'LGO', 'FO', 'PO', 'LO', 'RE24', 'WPA', 'WAR', 'GB_outs', 'FB_outs']
    neutral_cols = ['nPA', 'nAB', 'nH', 'nTB', 'nBB', 'nSF', 'nSH']
    regular_cols = ['PA', 'AB', 'H', 'TB', 'BB', 'SF', 'SH']

    # For seasons where neutral stats components are not available (NaN),
    # fall back to using the regular stat components for the career calculation.
    # Use 'nPA' as a proxy to determine if neutral stats components are available.
    if 'nPA' not in df.columns:
        df['nPA'] = pd.NA
    
    # Create a mask for rows (seasons) that are missing neutral stat components.
    no_neutral_stats_mask = pd.to_numeric(df['nPA'], errors='coerce').isna()
    
    # Map neutral columns to their regular counterparts.
    col_map = dict(zip(neutral_cols, regular_cols))

    for n_col, r_col in col_map.items():
        # Ensure the neutral column exists, creating it if necessary.
        if n_col not in df.columns:
            df[n_col] = pd.NA
        
        # For seasons identified by the mask, copy data from the regular column
        # to the neutral column. This ensures they are included in the career sum.
        if r_col in df.columns:
            df.loc[no_neutral_stats_mask, n_col] = df.loc[no_neutral_stats_mask, r_col]

    # Ensure neutral columns are numeric and fill any remaining NaNs with 0.
    for col in neutral_cols:
        if col not in df.columns:
            df[col] = 0
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df[neutral_cols] = df[neutral_cols].fillna(0)

    summed_stats = df[sum_cols + neutral_cols].sum()
    pa = summed_stats['PA']
    ab = summed_stats['AB']
    num_hits = summed_stats['H']
    num_walks = summed_stats['BB']
    num_sf = summed_stats['SF']
    num_tb = summed_stats['TB']
    num_hr = summed_stats['HR']
    num_strikeouts = summed_stats['K']
    num_sb = summed_stats['SB']
    num_cs = summed_stats['CS']
    num_rgo = summed_stats['RGO']
    num_lgo = summed_stats['LGO']
    num_gidp = summed_stats['GIDP']
    num_fo = summed_stats['FO']
    num_po = summed_stats['PO']
    num_lo = summed_stats['LO']
    avg = num_hits / ab if ab > 0 else 0
    obp = (num_hits + num_walks) / (ab + num_walks + num_sf) if (ab + num_walks + num_sf) > 0 else 0
    slg = num_tb / ab if ab > 0 else 0
    ops = obp + slg
    iso = slg - avg
    babip = (num_hits - num_hr) / (ab - num_strikeouts - num_hr + num_sf) if (ab - num_strikeouts - num_hr + num_sf) > 0 else 0
    sb_pct = num_sb / (num_sb + num_cs) if (num_sb + num_cs) > 0 else 0
    hr_pct = num_hr / pa if pa > 0 else 0
    so_pct = num_strikeouts / pa if pa > 0 else 0
    bb_pct = num_walks / pa if pa > 0 else 0
    num_gb_outs = num_rgo + num_lgo + num_gidp
    num_fb_outs = num_fo + num_po + num_lo + num_sf
    total_bip_outs = num_gb_outs + num_fb_outs
    gb_pct = num_gb_outs / total_bip_outs if total_bip_outs > 0 else 0
    fb_pct = num_fb_outs / total_bip_outs if total_bip_outs > 0 else 0
    gb_fb_ratio = num_gb_outs / num_fb_outs if num_fb_outs > 0 else 0

    # --- NEW: Calculate career nOBP and nSLG from summed neutral components ---
    career_nOBP = obp # Default to actual OBP
    career_nSLG = slg # Default to actual SLG

    if summed_stats['nPA'] > 0:
        n_ab = summed_stats['nAB']
        n_bb = summed_stats['nBB']
        n_sf = summed_stats['nSF']
        n_h = summed_stats['nH']
        n_tb = summed_stats['nTB']

        if (n_ab + n_bb + n_sf) > 0:
            career_nOBP = (n_h + n_bb) / (n_ab + n_bb + n_sf)
        if n_ab > 0:
            career_nSLG = n_tb / n_ab
    
    lg_obp_series = df['Season'].map(lambda s: league_stats_by_season.get(s, {}).get('lg_nOBP'))
    lg_slg_series = df['Season'].map(lambda s: league_stats_by_season.get(s, {}).get('lg_nSLG'))
    
    lg_obp_series = lg_obp_series.fillna(lg_obp_series.mean())
    lg_slg_series = lg_slg_series.fillna(lg_slg_series.mean())

    weighted_lg_obp = (lg_obp_series * df['PA']).sum()
    weighted_lg_slg = (lg_slg_series * df['PA']).sum()
    total_pa = df['PA'].sum()

    career_lg_obp = weighted_lg_obp / total_pa if total_pa > 0 else 0
    career_lg_slg = weighted_lg_slg / total_pa if total_pa > 0 else 0

    if career_lg_obp > 0 and career_lg_slg > 0:
        ops_plus = 100 * ((career_nOBP / career_lg_obp) + (career_nSLG / career_lg_slg) - 1)
    else:
        ops_plus = 100
    ops_plus = round(ops_plus)

    df = df.copy()
    df['weight'] = df['PA'] + df['SB'] + df['CS']
    weighted_avg_diff = (df['Avg Diff'] * df['weight']).sum()
    total_weight = df['weight'].sum()
    avg_diff = weighted_avg_diff / total_weight if total_weight > 0 else 0

    career_stats = summed_stats.copy()
    career_stats['AVG'] = avg
    career_stats['OBP'] = obp
    career_stats['SLG'] = slg
    career_stats['OPS'] = ops
    career_stats['ISO'] = iso
    career_stats['BABIP'] = babip
    career_stats['SB%'] = sb_pct
    career_stats['HR%'] = hr_pct
    career_stats['SO%'] = so_pct
    career_stats['BB%'] = bb_pct
    career_stats['GB%'] = gb_pct
    career_stats['FB%'] = fb_pct
    career_stats['GB/FB'] = gb_fb_ratio
    career_stats['OPS+'] = ops_plus
    career_stats['Avg Diff'] = avg_diff
    career_stats['nOBP'] = career_nOBP
    career_stats['nSLG'] = career_nSLG

    if include_type_column:
        season_stats = df[df['Season'].str.startswith('S')]
        player_type = None
        if not season_stats.empty:
            if 'Type' in season_stats.columns:
                unique_types = season_stats['Type'].dropna().unique()
                if len(unique_types) == 1:
                    player_type = unique_types[0]
        career_stats['Type'] = player_type

    return career_stats

def calculate_career_pitching_stats(df, league_n_era_by_season, include_type_column=True):

    summed_stats = df[['G', 'IP', 'BF', 'H', 'R', 'BB', 'IBB', 'Auto BB', 'K', 'HR', 'W', 'L', 'SV', 'HLD', 'GS', 'GF', 'CG', 'SHO', 'RE24', 'WPA', 'WAR', 'AB_A', 'SF_A', 'SH_A', '1B', '2B_A', '3B_A', 'RGO', 'LGO', 'FO', 'PO', 'LO', 'GB_outs_A', 'FB_outs_A', 'SB_A', 'CS_A']].sum()



    ip = summed_stats['IP']



    num_hits_allowed = summed_stats['H']



    num_walks_allowed = summed_stats['BB']



    runs_allowed = summed_stats['R']



    num_hr_allowed = summed_stats['HR']



    num_strikeouts = summed_stats['K']



    ab_against = summed_stats['AB_A']



    num_sf_allowed = summed_stats['SF_A']



    num_gb_outs_allowed = summed_stats['GB_outs_A']



    num_fb_outs_allowed = summed_stats['FB_outs_A']



    era = (runs_allowed * 6) / ip if ip > 0 else 0



    whip = (num_walks_allowed + num_hits_allowed) / ip if ip > 0 else 0



    h6 = (num_hits_allowed / ip) * 6 if ip > 0 else 0



    hr6 = (num_hr_allowed / ip) * 6 if ip > 0 else 0



    bb6 = (num_walks_allowed / ip) * 6 if ip > 0 else 0



    k6 = (num_strikeouts / ip) * 6 if ip > 0 else 0



    k_bb = num_strikeouts / num_walks_allowed if num_walks_allowed > 0 else 0



    baa = num_hits_allowed / ab_against if ab_against > 0 else 0



    obpa = (num_hits_allowed + num_walks_allowed) / summed_stats['BF'] if summed_stats['BF'] > 0 else 0



    tb_allowed = summed_stats['1B'] + 2*summed_stats['2B_A'] + 3*summed_stats['3B_A'] + 4*summed_stats['HR']



    slga = tb_allowed / ab_against if ab_against > 0 else 0



    opsa = obpa + slga



    babip_denom = ab_against - num_strikeouts - num_hr_allowed + num_sf_allowed



    babip_against = (num_hits_allowed - num_hr_allowed) / babip_denom if babip_denom > 0 else 0



    hr_pct_against = num_hr_allowed / summed_stats['BF'] if summed_stats['BF'] > 0 else 0



    k_pct_against = num_strikeouts / summed_stats['BF'] if summed_stats['BF'] > 0 else 0



    bb_pct_against = num_walks_allowed / summed_stats['BF'] if summed_stats['BF'] > 0 else 0



    total_fb_gb_allowed = num_fb_outs_allowed + num_gb_outs_allowed



    gb_pct_against = num_gb_outs_allowed / total_fb_gb_allowed if total_fb_gb_allowed > 0 else 0



    fb_pct_against = num_fb_outs_allowed / total_fb_gb_allowed if total_fb_gb_allowed > 0 else 0



    gb_fb_ratio_against = num_gb_outs_allowed / num_fb_outs_allowed if num_fb_outs_allowed > 0 else 0



    



    num_sb_allowed = summed_stats['SB_A']



    num_cs_against = summed_stats['CS_A']



    sb_pct_against = num_sb_allowed / (num_sb_allowed + num_cs_against) if (num_sb_allowed + num_cs_against) > 0 else 0







    weighted_fip = (df['FIP'] * df['IP']).sum()



    total_ip = df['IP'].sum()



    fip = weighted_fip / total_ip if total_ip > 0 else 0







    # New ERA- calculation



    df['lg_n_era'] = df['Season'].map(league_n_era_by_season)



    df['lg_n_era'] = df['lg_n_era'].fillna(df['lg_n_era'].mean())



    



    if 'nIP' in df.columns and 'nRuns' in df.columns:



        weighted_lg_n_era = (df['lg_n_era'] * df['nIP']).sum()



        total_n_ip = df['nIP'].sum()



        career_lg_n_era = weighted_lg_n_era / total_n_ip if total_n_ip > 0 else 0







        total_n_runs = df['nRuns'].sum()



        career_player_n_era = (total_n_runs * 6) / total_n_ip if total_n_ip > 0 else 0







        if career_lg_n_era > 0:



            era_minus = round(100 * (career_player_n_era / career_lg_n_era))



        else:



            era_minus = 100



    else: # Fallback for older cached data that might not have nIP/nRuns



        weighted_era_minus = (df['ERA-'] * df['IP']).sum()



        era_minus = weighted_era_minus / total_ip if total_ip > 0 else 0







    df = df.copy()

    df['weight'] = df['BF'] + df['SB_A'] + df['CS_A']

    weighted_avg_diff = (df['Avg Diff'] * df['weight']).sum()

    total_weight = df['weight'].sum()

    avg_diff = weighted_avg_diff / total_weight if total_weight > 0 else 0







    career_stats = summed_stats.copy()

    career_stats['ERA'] = era

    career_stats['WHIP'] = whip

    career_stats['H/6'] = h6

    career_stats['HR/6'] = hr6

    career_stats['BB/6'] = bb6

    career_stats['K/6'] = k6

    career_stats['K/BB'] = k_bb

    career_stats['BAA'] = baa

    career_stats['OBPA'] = obpa

    career_stats['SLGA'] = slga



    career_stats['OPSA'] = opsa



    career_stats['BABIP_A'] = babip_against



    career_stats['HR%_A'] = hr_pct_against



    career_stats['K%_A'] = k_pct_against



    career_stats['BB%_A'] = bb_pct_against



    career_stats['GB%_A'] = gb_pct_against



    career_stats['FB%_A'] = fb_pct_against



    career_stats['GB/FB_A'] = gb_fb_ratio_against



    career_stats['SB%_A'] = sb_pct_against



    career_stats['Avg Diff'] = avg_diff

    career_stats['FIP'] = fip

    career_stats['ERA-'] = era_minus

    career_stats['W-L%'] = summed_stats['W'] / (summed_stats['W'] + summed_stats['L']) if (summed_stats['W'] + summed_stats['L']) > 0 else 0



    if include_type_column:

        season_stats = df[df['Season'].str.startswith('S')]

        player_type = None

        if not season_stats.empty:

            if 'Type' in season_stats.columns:

                unique_types = season_stats['Type'].dropna().unique()

                if len(unique_types) == 1:

                    player_type = unique_types[0]

        career_stats['Type'] = player_type



    return career_stats

def get_base_state_svg(obc):



    """Generates a 2x2 diamond SVG for a given On-Base Code (OBC)."""



    bases = {



        'first': bool(obc & 1),



        'second': bool(obc & 2),



        'third': bool(obc & 4)



    }



    

    def diamond(filled, points):

        color = '#D7DADC' if filled else 'none'

        return f'<polygon points="{points}" fill="{color}" stroke="#D7DADC" stroke-width="1.5"/>'



    svg_parts = [

        '<svg width="24" height="24" viewbox="0 0 24 24">',

        diamond(bases['second'], "12,2 17,7 12,12 7,7"),   # 2nd base

        diamond(bases['third'], "5,9 10,14 5,19 0,14"),    # 3rd base

        diamond(bases['first'], "19,9 24,14 19,19 14,14"), # 1st base

        '</svg>'

    ]



    return "".join(svg_parts)


def generate_re_matrix_html(season_num):

    """Generates an HTML table for the RE matrix of a given season."""

    script_dir = os.path.dirname(os.path.abspath(__file__))



    cache_path = os.path.join(script_dir, '..', 'data', 'cache', f're_matrix_S{season_num}.csv')



    if not os.path.exists(cache_path):



        return None



    re_df = pd.read_csv(cache_path)



    matrix = {}

    for _, row in re_df.iterrows():

        matrix[(int(row['OBC']), int(row['Outs']))] = float(row['RunExpectancy'])



    html = "<table class='stats-table re-matrix'><thead><tr><th>Outs</th>"

    for obc in range(8):

        html += f"<th>{get_base_state_svg(obc)}</th>"

    html += "</tr></thead><tbody>"



    for outs in range(3):

        html += f"<tr><td><strong>{outs}</strong></td>"

        for obc in range(8):

            html += f"<td>{matrix.get((obc, outs), 0.0):.3f}</td>"

        html += "</tr>"

    html += "</tbody></table>"

    

    return {



        "title": f"Run Expectancy Matrix (S{season_num})",



        "content": html



    }

def _simulate_play_for_tracking(play, current_runners, outs):
    runs_scored = []
    runners = {k: v.copy() if v else None for k, v in current_runners.items()} # Deep copy
    batter = {'id': play['Hitter ID'], 'is_manfred': False}
    result = play['Exact Result'] if pd.notna(play['Exact Result']) else play['Old Result']
    advancement_bonus = 1 if outs == 2 and result in ['1B', '2B'] else 0

    # --- SIMULATE PLAY OUTCOME ---
    if result == 'HR':
        if runners[3]: runs_scored.append(runners[3])
        if runners[2]: runs_scored.append(runners[2])
        if runners[1]: runs_scored.append(runners[1])
        runs_scored.append(batter)
        runners = {1: None, 2: None, 3: None}
    elif result == '3B':
        if runners[3]: runs_scored.append(runners[3])
        if runners[2]: runs_scored.append(runners[2])
        if runners[1]: runs_scored.append(runners[1])
        runners = {1: None, 2: None, 3: batter}
    elif result == '2B':
        if runners[3]: runs_scored.append(runners[3])
        if runners[2]: runs_scored.append(runners[2])
        new_runners = {1: None, 2: batter, 3: None}
        if runners[1]: new_runners[3] = runners[1]
        runners = new_runners
    elif result in ['1B', 'BUNT 1B', 'Bunt 1B']:
        if advancement_bonus > 0 and result == '1B':
            if runners[3]: runs_scored.append(runners[3])
            if runners[2]: runs_scored.append(runners[2])
            if runners[1]: runners[3] = runners[1]
            runners = {1: batter, 2: None, 3: runners.get(1)}
        else:
            if runners[3]: runs_scored.append(runners[3])
            new_runners = {1: batter, 2: None, 3: None}
            if runners[2]: new_runners[3] = runners[2]
            if runners[1]: new_runners[2] = runners[1]
            runners = new_runners
    elif result in ['BB', 'IBB', 'Auto BB', 'AUTO BB']:
        if runners[1] and runners[2] and runners[3]: runs_scored.append(runners[3])
        new_runners = runners.copy()
        if runners[1] and runners[2]: new_runners[3] = runners[2]
        if runners[1]: new_runners[2] = runners[1]
        new_runners[1] = batter
        runners = new_runners
    # Add other out results here...

    return runs_scored, runners

def _get_simulated_runs_for_inning(inning_df):
    """Simulates an inning play-by-play based on rulebook logic to determine runs scored."""
    if inning_df.empty:
        return pd.Series([], dtype=int)

    # Mapping from OBC code to a list representing [1B, 2B, 3B]
    obc_to_runners = {
        0: [0, 0, 0], 1: [1, 0, 0], 2: [0, 1, 0], 3: [0, 0, 1],
        4: [1, 1, 0], 5: [1, 0, 1], 6: [0, 1, 1], 7: [1, 1, 1]
    }

    sim_runs_on_play = []
    
    # Get initial state from the first play
    initial_obc = inning_df['OBC'].iloc[0]
    initial_outs = inning_df['Outs'].iloc[0]
    
    runners = obc_to_runners.get(initial_obc, [0, 0, 0])
    outs = initial_outs
    
    for _, play in inning_df.iterrows():
        # The state for this play is the one we've been tracking
        runs_this_play = 0
        
        # Determine which result column to use
        use_old_results = play['Season'] in ['S2', 'S3']
        result = play['Old Result'] if use_old_results else play['Exact Result']

        # Two-out hit rule modifier
        advancement_bonus = 1 if outs == 2 and result in ['1B', '2B', '3B'] else 0

        # --- SIMULATE PLAY OUTCOME ---
        if result == 'HR':
            runs_this_play = sum(runners) + 1
            runners = [0, 0, 0]
        elif result == '3B':
            runs_this_play = sum(runners)
            runners = [0, 0, 1]
        elif result == '2B':
            if runners[2]: runs_this_play += 1 # Runner from 3rd scores
            if runners[1]: runs_this_play += 1 # Runner from 2nd scores
            runners = [0, 1, 1] if runners[0] else [0, 1, 0]
        elif result in ['1B', 'BUNT 1B', 'Bunt 1B']:
            new_runners = [0,0,0]
            if runners[2]: runs_this_play += 1
            if runners[1]: new_runners[2] = 1
            if runners[0]: new_runners[1] = 1
            new_runners[0] = 1
            runners = new_runners
            # Apply 2-out bonus
            if advancement_bonus > 0:
                if runners[2]: runs_this_play += 1; runners[2] = 0
                if runners[1]: runs_this_play += 1; runners[1] = 0
                if runners[0]: runners[2] = 1; runners[0] = 0

        elif result in ['BB', 'IBB', 'Auto BB', 'AUTO BB']:
            if runners[0] and runners[1] and runners[2]: runs_this_play += 1
            if runners[0] and runners[1]: runners[2] = 1
            if runners[0]: runners[1] = 1
            runners[0] = 1
        elif result in ['FO', 'Sac']:
            outs += 1
            if outs <= 2 and runners[2]: # Sac Fly
                runs_this_play += 1
                runners[2] = 0
        elif result in ['BUNT Sac', 'Bunt Sac', 'Bunt']:
            outs += 1
            if outs <= 2:
                # Runner on 2nd advances if 3rd is not occupied
                if runners[1] and not runners[2]:
                    runners[2] = 1
                    runners[1] = 0
                # Runner on 1st advances if 2nd is not occupied
                if runners[0] and not runners[1]:
                    runners[1] = 1
                    runners[0] = 0
        elif result in ['K', 'Auto K', 'Bunt K', 'AUTO K', 'PO', 'BUNT K']:
            outs += 1
        elif result == 'LO':
            outs += 1
            num_runners = sum(runners)
            if outs <= 2 and num_runners > 0:
                outs += 1 # Double Play
                # Trailing runner is out
                if runners[0]: runners[0] = 0
                elif runners[1]: runners[1] = 0
                else: runners[2] = 0
        elif result in ['LGO', 'RGO', 'BUNT GO', 'Bunt GO']:
            # Check for LGO Triple Play
            diff = pd.to_numeric(play['Diff'], errors='coerce')
            if result == 'LGO' and 496 <= diff <= 500 and outs == 0 and runners[0] and runners[1]:
                outs = 3
                runs_this_play = 0
                runners = [0, 0, 0]
            else:
                outs += 1
                is_lgo = result in ['LGO', 'BUNT GO', 'Bunt GO']
                # Double Play
                if outs <= 2 and runners[0]:
                    outs += 1
                    runners[0] = 0
                # Runner advancement on non-DP groundouts
                if outs <= 2:
                    if runners[2]: runs_this_play += 1; runners[2] = 0
                    if runners[1] and not (is_lgo and not runners[0]): runners[2] = 1; runners[1] = 0
        elif result == 'DP':
            # On a regular GIDP, a run can score from 3rd only if there are 0 outs.
            if outs == 0 and runners[2]:
                runs_this_play += 1
            outs += 2
            # Runner from 2nd advances to 3rd, other runners are out.
            if runners[1]:
                runners = [0, 0, 1]
            else:
                runners = [0, 0, 0]
        elif result == 'TP':
            outs = 3
            runs_this_play = 0 # No runs on TP
            runners = [0,0,0]

        sim_runs_on_play.append(runs_this_play)

        # Stop if inning is over
        if outs >= 3:
            # Fill remaining plays in this inning with 0 runs if any
            sim_runs_on_play.extend([0] * (len(inning_df) - len(sim_runs_on_play)))
            break
            
    return pd.Series(sim_runs_on_play, index=inning_df.index)

def get_run_expectancy_matrix(season, season_df, is_most_recent_season=False):
    """Calculates or loads a run expectancy matrix for a given season using a simulation engine."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, '..', 'data', 'cache')
    cache_path = os.path.join(data_dir, f're_matrix_{season}.csv')

    # Do not use cache for the most recent season, as it may be in progress.
    if os.path.exists(cache_path) and not is_most_recent_season:
        re_df = pd.read_csv(cache_path)
        re_matrix = {}
        for _, row in re_df.iterrows():
            re_matrix[(int(row['OBC']), int(row['Outs']))] = row['RunExpectancy']
        return re_matrix

    # Ensure key columns are numeric
    for col in ['OBC', 'Outs', 'Run']:
        season_df[col] = pd.to_numeric(season_df[col], errors='coerce').fillna(0).astype(int)

    # Get simulated runs for all innings
    simulated_runs = season_df.groupby('Inning ID').apply(_get_simulated_runs_for_inning, include_groups=False)
    season_df['SimulatedRuns'] = simulated_runs.reset_index(level=0, drop=True)

    all_plays = []
    for _, inning_df in season_df.groupby('Inning ID'):
        total_inning_runs = inning_df['SimulatedRuns'].sum()
        runs_scored_previously = inning_df['SimulatedRuns'].cumsum().shift(1).fillna(0)
        runs_after = total_inning_runs - runs_scored_previously

        temp_df = inning_df[['OBC', 'Outs']].copy()
        temp_df['RunsAfter'] = runs_after
        all_plays.append(temp_df)

    if not all_plays:
        return {}

    all_plays_df = pd.concat(all_plays)
    re_matrix_df = all_plays_df.groupby(['OBC', 'Outs'])['RunsAfter'].mean().reset_index()
    re_matrix_df.rename(columns={'RunsAfter': 'RunExpectancy'}, inplace=True)

    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    re_matrix_df.to_csv(cache_path, index=False)

    re_matrix = {}
    for _, row in re_matrix_df.iterrows():
        re_matrix[(row['OBC'], row['Outs'])] = row['RunExpectancy']
        
    return re_matrix


def _simulate_neutral_inning(inning_df, re_matrix):
    """Simulates a single inning based on 'Result at Neutral' to find neutral runs and outs,
    correctly attributing runs to pitchers and not charging for inherited runners."""
    obc_to_runners_map = {
        0: {1: None, 2: None, 3: None}, 1: {1: 'i', 2: None, 3: None},
        2: {1: None, 2: 'i', 3: None}, 3: {1: None, 2: None, 3: 'i'},
        4: {1: 'i', 2: 'i', 3: None}, 5: {1: 'i', 2: None, 3: 'i'},
        6: {1: None, 2: 'i', 3: 'i'}, 7: {1: 'i', 2: 'i', 3: 'i'}
    }

    def runners_to_obc(runners_dict, inherited_only=False):
        obc = 0
        if runners_dict.get(1) and (not inherited_only or runners_dict[1] == 'i'): obc |= 1
        if runners_dict.get(2) and (not inherited_only or runners_dict[2] == 'i'): obc |= 2
        if runners_dict.get(3) and (not inherited_only or runners_dict[3] == 'i'): obc |= 4
        return obc

    initial_obc = inning_df['OBC'].iloc[0]
    runners = obc_to_runners_map.get(initial_obc, {1: None, 2: None, 3: None}).copy()
    outs = inning_df['Outs'].iloc[0]
    total_n_runs = 0

    for _, play in inning_df.iterrows():
        if outs >= 3:
            break

        result = play['Result at Neutral']
        if pd.isna(result):
            result = play['Old Result']
        
        batter = 'p'

        if result == 'HR':
            if runners.get(3) == 'p': total_n_runs += 1
            if runners.get(2) == 'p': total_n_runs += 1
            if runners.get(1) == 'p': total_n_runs += 1
            total_n_runs += 1
            runners = {1: None, 2: None, 3: None}
        elif result == '3B':
            if runners.get(3) == 'p': total_n_runs += 1
            if runners.get(2) == 'p': total_n_runs += 1
            if runners.get(1) == 'p': total_n_runs += 1
            runners = {1: None, 2: None, 3: batter}
        elif result == '2B':
            if runners.get(3) == 'p': total_n_runs += 1
            if runners.get(2) == 'p': total_n_runs += 1
            new_runners = {1: None, 2: batter, 3: None}
            if runners.get(1): new_runners[3] = runners[1]
            runners = new_runners
        elif result in ['1B', 'BUNT 1B']:
            if runners.get(3) == 'p': total_n_runs += 1
            new_runners = {1: batter, 2: None, 3: None}
            if runners.get(2): new_runners[3] = runners[2]
            if runners.get(1): new_runners[2] = runners[1]
            runners = new_runners
        elif result in ['BB', 'IBB', 'Auto BB', 'AUTO BB']:
            if runners.get(1) and runners.get(2) and runners.get(3):
                if runners[3] == 'p': total_n_runs += 1
            new_runners = runners.copy()
            if runners.get(1) and runners.get(2): new_runners[3] = runners[2]
            if runners.get(1): new_runners[2] = runners[1]
            new_runners[1] = batter
            runners = new_runners
        elif result in ['FO', 'Sac']:
            outs += 1
            if outs < 3 and runners.get(3):
                if runners[3] == 'p': total_n_runs += 1
                runners[3] = None
        elif result in ['Bunt', 'BUNT Sac']:
            outs += 1
            if outs < 3:
                if runners.get(2) and not runners.get(3):
                    runners[3] = runners[2]
                    runners[2] = None
                if runners.get(1) and not runners.get(2):
                    runners[2] = runners[1]
                    runners[1] = None
        elif result in ['K', 'Auto K', 'Bunt K', 'AUTO K', 'PO']:
            outs += 1
        elif result in ['LGO', 'RGO', 'BUNT GO', 'Sac']:
            if outs < 2 and runners.get(1):
                outs += 2
                runners[1] = None
                if outs < 3:
                    if runners.get(3) == 'p': total_n_runs += 1
                    runners[3] = runners.get(2)
                    runners[2] = None
            else:
                outs += 1
                if outs < 3:
                    if runners.get(3) == 'p': total_n_runs += 1
                    runners[3] = runners.get(2)
                    runners[2] = runners.get(1)
                    runners[1] = None
        elif result == 'DP':
            outs += 2
        elif result == 'TP':
            outs = 3

    if outs < 3:
        final_obc = runners_to_obc(runners)
        inherited_final_obc = runners_to_obc(runners, inherited_only=True)
        
        re_total = re_matrix.get((final_obc, outs), 0)
        re_inherited = re_matrix.get((inherited_final_obc, outs), 0)
        
        re_pitcher_responsibility = re_total - re_inherited
        if re_pitcher_responsibility > 0:
            total_n_runs += re_pitcher_responsibility

    return pd.Series({'nRuns': total_n_runs, 'nOuts': outs if outs <= 3 else 3})

def calculate_neutral_pitching_stats(df, re_matrix):
    """Calculates total neutral runs and outs for a pitcher's season."""
    if df.empty or not re_matrix:
        return pd.Series({'nRuns': 0, 'nOuts': 0})
    
    # This will be slow, but it's the only way to do it row-by-row
    inning_stats = df.groupby('Inning ID').apply(lambda x: _simulate_neutral_inning(x, re_matrix), include_groups=False)
    return inning_stats.sum()

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

def calculate_games_started(df):
    achievements = []
    game_groups = list(df.groupby(['Season', 'Game ID']))
    num_games = len(game_groups)
    print(f"Calculating games started for {num_games} games...")

    for i, ((season, game_id), game_df) in enumerate(game_groups):
        if (i + 1) % 100 == 0:
            print(f"  ... processed {i + 1} / {num_games} games for GS")

        teams_in_game = game_df['Batter Team'].unique()
        if len(teams_in_game) != 2:
            continue
        
        team_A, team_B = teams_in_game[0], teams_in_game[1]

        pitchers_A = game_df[game_df['Pitcher Team'] == team_A]['Pitcher ID'].unique().tolist()
        pitchers_B = game_df[game_df['Pitcher Team'] == team_B]['Pitcher ID'].unique().tolist()

        if pitchers_A:
            starter_id_A = game_df[game_df['Pitcher Team'] == team_A]['Pitcher ID'].iloc[0]
            achievements.append({'Season': season, 'Pitcher ID': starter_id_A, 'Stat': 'GS', 'Team': team_A})

        if pitchers_B:
            starter_id_B = game_df[game_df['Pitcher Team'] == team_B]['Pitcher ID'].iloc[0]
            achievements.append({'Season': season, 'Pitcher ID': starter_id_B, 'Stat': 'GS', 'Team': team_B})
    
    if not achievements: return pd.DataFrame(columns=['Season', 'Pitcher ID', 'Team', 'GS'])

    achievements_df = pd.DataFrame(achievements)
    agg_df = achievements_df.groupby(['Season', 'Pitcher ID', 'Team', 'Stat']).size().unstack(fill_value=0).reset_index()

    if 'GS' not in agg_df.columns:
        agg_df['GS'] = 0

    return agg_df[['Season', 'Pitcher ID', 'Team', 'GS']]

def calculate_game_achievements(df):
    achievements = []
    game_groups = list(df.groupby(['Season', 'Game ID']))
    num_games = len(game_groups)
    print(f"Calculating achievements for {num_games} games...")

    for i, ((season, game_id), game_df) in enumerate(game_groups):
        if (i + 1) % 100 == 0:
            print(f"  ... processed {i + 1} / {num_games} games for achievements")
        
        teams_in_game = game_df['Batter Team'].unique()
        if len(teams_in_game) != 2:
            continue

        team_A, team_B = teams_in_game[0], teams_in_game[1]

        runs_A = game_df[game_df['Batter Team'] == team_A]['Run'].sum()
        runs_B = game_df[game_df['Batter Team'] == team_B]['Run'].sum()

        pitchers_A = game_df[game_df['Pitcher Team'] == team_A]['Pitcher ID'].unique().tolist()
        pitchers_B = game_df[game_df['Pitcher Team'] == team_B]['Pitcher ID'].unique().tolist()

        if pitchers_A:
            finisher_id_A = game_df[game_df['Pitcher Team'] == team_A]['Pitcher ID'].iloc[-1]
            achievements.append({'Season': season, 'Pitcher ID': finisher_id_A, 'Stat': 'GF', 'Team': team_A})

            if len(pitchers_A) == 1:
                pitcher_id = pitchers_A[0]
                achievements.append({'Season': season, 'Pitcher ID': pitcher_id, 'Stat': 'CG', 'Team': team_A})
                
                if runs_B == 0:
                    achievements.append({'Season': season, 'Pitcher ID': pitcher_id, 'Stat': 'SHO', 'Team': team_A})

        if pitchers_B:
            finisher_id_B = game_df[game_df['Pitcher Team'] == team_B]['Pitcher ID'].iloc[-1]
            achievements.append({'Season': season, 'Pitcher ID': finisher_id_B, 'Stat': 'GF', 'Team': team_B})

            if len(pitchers_B) == 1:
                pitcher_id = pitchers_B[0]
                achievements.append({'Season': season, 'Pitcher ID': pitcher_id, 'Stat': 'CG', 'Team': team_B})

                if runs_A == 0:
                    achievements.append({'Season': season, 'Pitcher ID': pitcher_id, 'Stat': 'SHO', 'Team': team_B})

    if not achievements: return pd.DataFrame(columns=['Season', 'Pitcher ID', 'Team', 'GF', 'CG', 'SHO'])

    achievements_df = pd.DataFrame(achievements)
    
    agg_df = achievements_df.groupby(['Season', 'Pitcher ID', 'Team', 'Stat']).size().unstack(fill_value=0).reset_index()

    for col in ['GF', 'CG', 'SHO']:
        if col not in agg_df.columns:
            agg_df[col] = 0
            
    return agg_df[['Season', 'Pitcher ID', 'Team', 'GF', 'CG', 'SHO']]


def preprocess_gamelogs_for_stat_corrections(df, player_id_to_name_map):
    """
    Processes a DataFrame of all gamelogs to correct stat attribution for pinch runners
    and multi-steal events. This is a major pre-processing step.
    """
    
    steal_events = {'STEAL 2B', 'STEAL 3B', 'Steal 2B', 'Steal 3B', 'MSTEAL 3B', 'MSteal 3B', 'CS 2B', 'CS 3B', 'CS Home', 'CMS 3B', 'CMS Home'}
    multi_steal_events = {'MSTEAL 3B', 'MSteal 3B', 'CMS 3B', 'CMS Home'}
    
    corrected_rows = []
    
    for game_id, game_df in df.groupby(['Season', 'Game ID']):
        
        game_df = game_df.sort_values(by=['Inning', 'PA of Inning']).copy()
        
        runners = {1: None, 2: None, 3: None} # base -> player_id
        player_on_base_map = {} # player_id -> base
        
        new_rows_for_game = []

        for index, play in game_df.iterrows():
            current_runners = runners.copy()
            
            player_id = play['Hitter ID']
            result = play['Exact Result']
            
            is_steal_event = result in steal_events
            is_batter_on_base = player_id in player_on_base_map
            
            if is_steal_event and not is_batter_on_base:
                # This player is a pinch runner. Find who they replaced.
                original_runner_id = None
                if result in ['STEAL 2B', 'CS 2B']:
                    original_runner_id = runners[1]
                    if original_runner_id: runners[1] = player_id
                elif result in ['STEAL 3B', 'CS 3B', 'MSTEAL 3B', 'MSteal 3B', 'CMS 3B']:
                    original_runner_id = runners[2]
                    if original_runner_id: runners[2] = player_id
                elif result in ['CS Home', 'CMS Home']:
                    original_runner_id = runners[3]
                    if original_runner_id: runners[3] = player_id

                if original_runner_id:
                    # If the original runner was credited with a run, move it to the pinch runner.
                    on_base_events = {'1B', '2B', '3B', 'HR', 'BB', 'IBB', 'BUNT 1B', 'Bunt 1B'}
                    original_runner_pa_mask = (
                        (df['Season'] == game_id[0]) &
                        (df['Game ID'] == game_id[1]) &
                        (df.index < index) &
                        (df['Hitter ID'] == original_runner_id) &
                        (df['Old Result'].isin(on_base_events) | df['Exact Result'].isin(on_base_events))
                    )
                    original_runner_pa_rows = df[original_runner_pa_mask]

                    if not original_runner_pa_rows.empty:
                        original_pa_row_index = original_runner_pa_rows.index[-1]
                        if df.loc[original_pa_row_index, 'Run'] == 1:
                            df.loc[original_pa_row_index, 'Run'] = 0
                            df.loc[index, 'Run'] = 1

                    # Update the map for future lookups
                    if original_runner_id in player_on_base_map:
                        base = player_on_base_map.pop(original_runner_id)
                        player_on_base_map[player_id] = base
                    
                    # Find all future plays for the original runner and re-assign them
                    mask = (df['Season'] == game_id[0]) & (df['Game ID'] == game_id[1]) & (df.index > index) & (df['Hitter ID'] == original_runner_id)
                    df.loc[mask, 'Hitter ID'] = player_id

            # --- Multi-Steal SB Attribution ---
            if result in multi_steal_events:
                is_caught_steal = result.startswith('CMS')
                caught_runner = player_id if is_caught_steal else None

                for base, runner_id in current_runners.items():
                    if runner_id and runner_id != caught_runner:
                        # This is a successful trailing runner. Award SB.
                        new_row = play.copy()
                        new_row['Hitter ID'] = runner_id
                        new_row['Hitter'] = player_id_to_name_map.get(runner_id, 'Unknown Player')
                        # Determine the type of steal based on the base they are advancing to
                        new_row['Exact Result'] = f'STEAL {base + 1}B' if base < 3 else 'STEAL Home'
                        new_rows_for_game.append(new_row)

            # --- Update runner state for the NEXT play ---
            # This is a simplified simulation just for tracking who is on base.
            # It does not need to be perfect because we only use it for PR/CMS identification.
            batter_id = play['Hitter ID']
            
            # Clear bases
            runners = {1: None, 2: None, 3: None}
            player_on_base_map.clear()

            # Place batter if they reached base
            if play['Old Result'] in {'1B', '2B', '3B', 'HR', 'BB', 'IBB'} or play['Exact Result'] in {'BUNT 1B', 'Bunt 1B'}:
                if play['Old Result'] == '1B' or play['Exact Result'] in {'BUNT 1B', 'Bunt 1B', 'BB', 'IBB'}:
                    runners[1] = batter_id
                elif play['Old Result'] == '2B':
                    runners[2] = batter_id
                elif play['Old Result'] == '3B':
                    runners[3] = batter_id
            
            # Place runners based on OBC After. This is tricky without knowing who is who.
            # This part of the logic is imperfect but is a best-effort for tracking.
            # The key part (PR substitution) happens before this state update.
            
        corrected_rows.extend(new_rows_for_game)

    if corrected_rows:
        return pd.concat([df, pd.DataFrame(corrected_rows)], ignore_index=True)
    
    return df

def aggregate_decisions(df, games_df):
    if df.empty: return pd.DataFrame(columns=['Season', 'Pitcher ID', 'Team', 'W', 'L', 'SV', 'HLD'])

    base_df = games_df[['Season', 'Pitcher ID', 'Pitcher Team']].drop_duplicates().rename(columns={'Pitcher Team': 'Team'})
    pitcher_teams_in_game = games_df[['Season', 'Game ID', 'Pitcher ID', 'Pitcher Team']].drop_duplicates().rename(columns={'Pitcher Team': 'Team'})

    def get_agg_stat(decision_col, stat_name):
        stat_df = df[df[decision_col].notna()][['Season', 'Game ID', decision_col]].rename(columns={decision_col: 'Pitcher ID'})
        stat_with_teams = stat_df.merge(pitcher_teams_in_game, on=['Season', 'Game ID', 'Pitcher ID'], how='left')
        return stat_with_teams.groupby(['Season', 'Pitcher ID', 'Team']).size().reset_index(name=stat_name)

    wins_agg = get_agg_stat('win', 'W')
    losses_agg = get_agg_stat('loss', 'L')
    saves_agg = get_agg_stat('save', 'SV')

    if 'holds' in df.columns and not df.explode('holds').dropna(subset=['holds']).empty:
        holds_exploded = df.explode('holds').dropna(subset=['holds'])
        holds_df = holds_exploded[['Season', 'Game ID', 'holds']].rename(columns={'holds': 'Pitcher ID'})
        holds_with_teams = holds_df.merge(pitcher_teams_in_game, on=['Season', 'Game ID', 'Pitcher ID'], how='left')
        holds_agg = holds_with_teams.groupby(['Season', 'Pitcher ID', 'Team']).size().reset_index(name='HLD')
    else:
        holds_agg = pd.DataFrame(columns=['Season', 'Pitcher ID', 'Team', 'HLD'])

    agg_df = base_df
    for stat_df in [wins_agg, losses_agg, saves_agg, holds_agg]:
        if not stat_df.empty:
            stat_df['Pitcher ID'] = pd.to_numeric(stat_df['Pitcher ID'], errors='coerce').dropna().astype(int)
            agg_df = agg_df.merge(stat_df, on=['Season', 'Pitcher ID', 'Team'], how='left')

    for col in ['W', 'L', 'SV', 'HLD']:
        if col not in agg_df.columns:
            agg_df[col] = 0
        agg_df[col] = agg_df[col].fillna(0).astype(int)
        
    return agg_df

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
            
            # Drop duplicates, keeping the first occurrence
            df.drop_duplicates(subset=['player_id'], keep='first', inplace=True)
            
            df.set_index('player_id', inplace=True)
            df = df.where(pd.notnull(df), None)
            
            # Convert to dict and update player_info, ensuring we don't overwrite with None
            new_data = df.to_dict('index')
            for pid, data in new_data.items():
                if pid not in player_info:
                    player_info[pid] = {}
                for key, value in data.items():
                    if value is not None:
                        player_info[pid][key] = value

    # Save the combined player info to a JSON file
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'data', 'player_info.json')
    with open(output_path, 'w') as f:
        json.dump(player_info, f)

    # The following code block is commented out because the user wants to manually edit the type_definitions.json file.
    # To regenerate the file, uncomment this block.
    # all_batting_types = set()
    # all_pitching_types = set()
    # if player_type_data:
    #     for season in player_type_data:
    #         df = player_type_data[season]
    #         all_batting_types.update(df['Batting Type'].dropna().unique())
    #         all_pitching_types.update(df['Pitching Type'].dropna().unique())
    #
    # type_definitions = {
    #     'batting': {t: f"Description for {t}" for t in sorted(list(all_batting_types))},
    #     'pitching': {t: f"Description for {t}" for t in sorted(list(all_pitching_types))}
    # }
    #
    # output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'data', 'type_definitions.json')
    # with open(output_path, 'w') as f:
    #     json.dump(type_definitions, f, indent=4)
    # print(f"Type definitions saved to {output_path}")

    print("Reconciling player IDs across seasons...")
    # Reconcile player IDs
    # This is a bit of a mess, but it works.

    # Create a map of player names to their IDs and seasons from the data
    hitters_with_ids = combined_df[combined_df['Hitter ID'].notna()][['Hitter ID', 'Hitter', 'Season']].rename(columns={'Hitter ID': 'Player ID', 'Hitter': 'Player Name'})
    pitchers_with_ids = combined_df[combined_df['Pitcher ID'].notna()][['Pitcher ID', 'Pitcher', 'Season']].rename(columns={'Pitcher ID': 'Player ID', 'Pitcher': 'Player Name'})
    players_with_ids = pd.concat([hitters_with_ids, pitchers_with_ids]).drop_duplicates()
    players_with_ids['Player ID'] = players_with_ids['Player ID'].astype(int)
    
    name_to_id_season_map = defaultdict(lambda: defaultdict(set))
    for _, row in players_with_ids.iterrows():
        name_to_id_season_map[row['Player Name']][row['Player ID']].add(row['Season'])

    # Function to find a matching ID from an adjacent season
    def find_adjacent_id(player_name, season_str):
        if player_name in name_to_id_season_map:
            season_num = int(season_str.replace('S', ''))
            # Check S, S+1, S-1 for a valid ID
            for s_offset in [0, 1, -1]:
                adj_season_num = season_num + s_offset
                for pid, seasons in name_to_id_season_map[player_name].items():
                    if f"S{adj_season_num}" in seasons:
                        return pid
        return None

    # Apply the logic to fill missing IDs
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

    # Initialize global temporary ID management for any remaining missing IDs
    global_temp_id_counter = -1
    player_name_to_temp_id = {} # Maps player name to a consistent negative ID

    def get_or_assign_temp_id(player_name):
        nonlocal global_temp_id_counter
        if player_name not in player_name_to_temp_id:
            player_name_to_temp_id[player_name] = global_temp_id_counter
            global_temp_id_counter -= 1
        return player_name_to_temp_id[player_name]

    # Apply temporary IDs for any players still missing one
    no_id_mask = combined_df['Pitcher ID'].isna()
    if no_id_mask.any():
        combined_df.loc[no_id_mask, 'Pitcher ID'] = combined_df.loc[no_id_mask, 'Pitcher'].apply(get_or_assign_temp_id)

    no_id_mask_hitter = combined_df['Hitter ID'].isna()
    if no_id_mask_hitter.any():
        combined_df.loc[no_id_mask_hitter, 'Hitter ID'] = combined_df.loc[no_id_mask_hitter, 'Hitter'].apply(get_or_assign_temp_id)

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gamelogs_path = os.path.join(script_dir, '..', 'data', 'gamelogs.txt')
        with open(gamelogs_path, 'r') as f: gamelogs_content = f.read()
        season_games_map = {parts[0]: int(parts[1]) for line in gamelogs_content.splitlines() if len(parts := line.strip().split('\t')) >= 2}
    except FileNotFoundError:
        print("Warning: gamelogs.txt not found. Cannot filter for regular season games.")
        season_games_map = {}

    if season_games_map:
        season_games_series = combined_df['Season'].map(season_games_map)
        combined_df = combined_df[combined_df['Session'] <= season_games_series].copy()
        print(f"Filtered to {len(combined_df.groupby(['Season', 'Game ID']))} regular season games.")

    # Create the PA of Inning column needed for sorting
    combined_df['PA of Inning'] = combined_df.groupby(['Season', 'Game ID', 'Inning']).cumcount()

    print("Applying manual gamelog corrections...")
    # The lambda function calls our correction function for each group (game)
    # and passes the group's name (a tuple of season and game_id) as an argument.
    combined_df = combined_df.groupby(['Season', 'Game ID']).apply(
        lambda g: apply_gamelog_corrections(g, g.name), include_groups=False
    ).reset_index()
    print("Gamelog corrections applied.")

    # Exclude in-progress games from the most recent season for pitching decisions
    decision_games_df = combined_df.copy()
    if most_recent_season:
        most_recent_season_df = combined_df[combined_df['Season'] == most_recent_season]
        if not most_recent_season_df.empty:
            max_session = most_recent_season_df['Session'].max()
            print(f"Excluding games from session {max_session} of {most_recent_season} from pitching decision calculations.")
            decision_games_mask = ~((combined_df['Season'] == most_recent_season) & (combined_df['Session'] == max_session))
            decision_games_df = combined_df[decision_games_mask]

    # Calculate pitching decisions on the filtered data
    print("Calculating pitching decisions (W, L, SV, HLD)...")
    pitching_decisions = []
    game_groups = list(decision_games_df.groupby(['Season', 'Game ID']))
    num_games = len(game_groups)
    print(f"  Processing {num_games} games for decisions...")
    for i, ((season, game_id), game_df) in enumerate(game_groups):
        if (i + 1) % 100 == 0:
            print(f"  ... {i + 1} / {num_games} games processed")
        decisions = get_pitching_decisions(game_df, season)
        if decisions:
            decisions['Season'] = season
            decisions['Game ID'] = game_id
            pitching_decisions.append(decisions)
    pitching_decisions_df = pd.DataFrame(pitching_decisions)
    game_types = combined_df[['Season', 'Game ID', 'GameType']].drop_duplicates()
    pitching_decisions_df = pitching_decisions_df.merge(game_types, on=['Season', 'Game ID'], how='left')
    regular_season_decisions = pitching_decisions_df[pitching_decisions_df['GameType'] == 'Regular']
    regular_pitcher_stats_agg = aggregate_decisions(regular_season_decisions, combined_df)

    # Flag unearned runs from Manfred runners
    # combined_df = flag_unearned_runs(combined_df)

    all_players = pd.concat([
        combined_df[['Hitter ID', 'Hitter', 'Season', 'Session']].rename(columns={'Hitter ID': 'Player ID', 'Hitter': 'Player Name'})
        ,
        combined_df[['Pitcher ID', 'Pitcher', 'Season', 'Session']].rename(columns={'Pitcher ID': 'Player ID', 'Pitcher': 'Player Name'})
    ])
    all_players.dropna(subset=['Player ID', 'Player Name'], inplace=True)
    all_players['Player ID'] = all_players['Player ID'].astype(int)
    all_players['Season_num'] = all_players['Season'].str.replace('S', '').astype(int)
    all_players.sort_values(by=['Season_num', 'Session'], ascending=[False, False], inplace=True)
    
    player_names = all_players.groupby('Player ID')['Player Name'].apply(lambda x: list(dict.fromkeys(x))).to_dict()

    player_id_map = {}
    for player_id, names in player_names.items():
        if player_id == 0: continue
        if not names: continue
        
        # With reverse-chronological sort, the first unique name is the most recent.
        current_name = names[0]
        former_names = names[1:]

        # If the most recent name is "IMPORT ERROR", try to use the next one.
        if current_name == "IMPORT ERROR" and len(names) > 1:
            current_name = names[1]
            former_names = names[2:]
        
        player_id_map[int(player_id)] = {
            'currentName': current_name,
            'formerNames': former_names
        }
    
    player_id_to_name_map = {k: v['currentName'] for k, v in player_id_map.items()}

    # Apply corrections for pinch runners and multi-steals
    print("Pre-processing gamelogs for stat corrections...")
    combined_df = preprocess_gamelogs_for_stat_corrections(combined_df, player_id_to_name_map)
    print("Pre-processing complete.")

    # Disambiguate Line Outs (LO) from Left Ground Outs (LGO) in modern seasons.
    is_modern_season = ~combined_df['Season'].isin(['S2', 'S3'])
    lo_mask = (combined_df['Exact Result'] == 'LGO') & (combined_df['Old Result'] == 'LO')
    combined_df.loc[is_modern_season & lo_mask, 'Exact Result'] = 'LO'

    # Ensure key numeric columns are treated as numbers, filling non-numeric with 0
    combined_df['RBI'] = pd.to_numeric(combined_df['RBI'], errors='coerce').fillna(0)
    combined_df['Run'] = pd.to_numeric(combined_df['Run'], errors='coerce').fillna(0)
    if 'Batter WPA' in combined_df.columns:
        combined_df['Batter WPA'] = pd.to_numeric(combined_df['Batter WPA'].astype(str).str.strip('%'), errors='coerce').fillna(0) / 100
    if 'Pitcher WPA' in combined_df.columns:
        combined_df['Pitcher WPA'] = pd.to_numeric(combined_df['Pitcher WPA'].astype(str).str.strip('%'), errors='coerce').fillna(0) / 100

    combined_df['Pitcher ID'] = pd.to_numeric(combined_df['Pitcher ID'], errors='coerce').fillna(0).astype(int)
    combined_df['Hitter ID'] = pd.to_numeric(combined_df['Hitter ID'], errors='coerce').fillna(0).astype(int)
    combined_df['Season_num'] = combined_df['Season'].str.replace('S', '').astype(int)
    combined_df.sort_values(by=['Season_num', 'Session'], ascending=[True, True], inplace=True)
    combined_df.drop(columns=['Season_num'], inplace=True)
    
    print("Processing Run Expectancy Matrices...")
    run_expectancy_by_season = {}
    all_season_names = combined_df['Season'].unique()
    if all_season_names.size > 0:
        most_recent_season_num = max([int(s.replace('S', '')) for s in all_season_names])
        most_recent_season = f"S{most_recent_season_num}"
    else:
        most_recent_season = ""

    sorted_seasons = sorted(all_season_names, key=lambda s: int(s.replace('S', '')))
    for season in sorted_seasons:
        season_df = combined_df[combined_df['Season'] == season]
        is_current = (season == most_recent_season)
        if is_current: print(f"Calculating matrix for current season {season} (will not use cache)...")
        run_expectancy_by_season[season] = get_run_expectancy_matrix(season, season_df.copy(), is_most_recent_season=is_current)
    print("Run Expectancy Matrices are ready.")

    print("Calculating RE24 for all plays...")
    from game_processing import Game

    re24_values = []
    for season in sorted_seasons:
        season_df = combined_df[combined_df['Season'] == season].copy()
        re_matrix = run_expectancy_by_season.get(season, {})
        if not re_matrix:
            re24_values.append(pd.Series(0, index=season_df.index))
            continue

        game_simulator = Game(pd.DataFrame(), season)

        season_df['OBC'] = pd.to_numeric(season_df['OBC'], errors='coerce').fillna(0).astype(int)
        season_df['Outs'] = pd.to_numeric(season_df['Outs'], errors='coerce').fillna(0).astype(int)
        re_before = season_df.apply(lambda row: re_matrix.get((row['OBC'], row['Outs']), 0), axis=1)

        inning_groups = season_df.groupby('Inning ID')
        obc_after_raw = inning_groups['OBC'].shift(-1)
        outs_after_raw = inning_groups['Outs'].shift(-1)
        obc_after_raw_for_sim = inning_groups['OBC'].shift(-1).fillna(0).astype(int)

        last_play_of_game_mask = ~season_df.duplicated(subset='Game ID', keep='last')
        
        runners_map = {0:[False,False,False], 1:[True,False,False], 2:[False,True,False], 3:[False,False,True], 4:[True,True,False], 5:[True,False,True], 6:[False,True,True], 7:[True,True,True]}
        
        def get_re24_components(row):
            runners_before = runners_map.get(row['OBC'], [False, False, False])
            result = row['Exact Result'] if pd.notna(row['Exact Result']) else row['Old Result']
            diff_val = pd.to_numeric(row.get('Diff'), errors='coerce')
            diff = int(diff_val if pd.notna(diff_val) else 0)
            pa_type_val = pd.to_numeric(row.get('PA Type'), errors='coerce')
            pa_type = int(pa_type_val if pd.notna(pa_type_val) else 0)
            
            new_runners, runs_on_play, outs_for_play = game_simulator._simulate_play(
                row['obc_after_for_sim'], runners_before, row['Outs'], result, row['Old Result'],
                diff, int(row['Season'].replace('S','')), pa_type
            )
            
            outs_after = row['Outs'] + outs_for_play
            
            is_last_play_of_inning = pd.isna(row['obc_after_raw'])

            if outs_after >= 3 or is_last_play_of_inning:
                re_after = 0
            else:
                obc_after = game_simulator._runners_to_obc(tuple(new_runners))
                re_after = re_matrix.get((obc_after, outs_after), 0)
                
            return pd.Series([re_after, runs_on_play])

        temp_df = season_df.copy()
        temp_df['obc_after_raw'] = obc_after_raw
        temp_df['outs_after_raw'] = outs_after_raw
        temp_df['obc_after_for_sim'] = obc_after_raw_for_sim
        temp_df['is_last_play_of_game'] = last_play_of_game_mask
        
        re24_components = temp_df.apply(get_re24_components, axis=1)
        re24_components.columns = ['re_after', 'runs_on_play']
        
        re_after = re24_components['re_after']
        runs_on_play = re24_components['runs_on_play']
        
        re_after.index = season_df.index
        runs_on_play.index = season_df.index

        season_re24 = re_after - re_before + runs_on_play
        re24_values.append(season_re24)

    if re24_values:
        combined_df['RE24'] = pd.concat(re24_values)
    else:
        combined_df['RE24'] = 0
    print("RE24 calculation complete.")



    combined_df['Season_num'] = combined_df['Season'].str.replace('S', '').astype(int)
    combined_df.sort_values(by=['Season_num', 'Session'], ascending=[True, True], inplace=True)
    combined_df.drop(columns=['Season_num'], inplace=True)

    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'cache')
    previous_most_recent = _read_cache_manifest(cache_dir)
    seasons_to_recalc = []
    if most_recent_season != previous_most_recent and previous_most_recent is not None:
        print(f"New season detected. Finalizing stats cache for {previous_most_recent}...")
        seasons_to_recalc.append(previous_most_recent)

    print("Calculating all player stats and decisions (using cache for past seasons)...")

    leaderboard_df = combined_df

    # --- Pre-calculate all stats that need to be merged before caching ---
    print("Calculating FIP constants...")
    fip_constants_by_season = {}
    league_pitching_totals = leaderboard_df.groupby('Season').apply(lambda df: calculate_pitching_stats(df, season=df.name), include_groups=False).reset_index()
    if not league_pitching_totals.empty:
        league_pitching_totals['lg_ERA'] = (league_pitching_totals['R'] * 6) / league_pitching_totals['IP']
        league_pitching_totals['lg_FIP_unscaled'] = ((13 * league_pitching_totals['HR']) + (3 * league_pitching_totals['BB']) - (2 * league_pitching_totals['K'])) / league_pitching_totals['IP']
        league_pitching_totals['FIP_Constant'] = league_pitching_totals['lg_ERA'] - league_pitching_totals['lg_FIP_unscaled']
        fip_constants_by_season = league_pitching_totals.set_index('Season')['FIP_Constant'].to_dict()

    print("Calculating Neutral ERA and ERA-...")
    league_n_era_by_season = {}
    neutral_pitching_stats = []
    for season in sorted_seasons:
        season_df = leaderboard_df[leaderboard_df['Season'] == season]
        re_matrix = run_expectancy_by_season.get(season, {})
        if not re_matrix: continue
        lg_neutral_stats = calculate_neutral_pitching_stats(season_df, re_matrix)
        lg_n_ip = lg_neutral_stats['nOuts'] / 3
        lg_n_era = (lg_neutral_stats['nRuns'] * 6) / lg_n_ip if lg_n_ip > 0 else 0
        league_n_era_by_season[season] = lg_n_era
        
        # Calculate per-team ERA-
        for (pitcher_id, team), player_team_df in season_df.groupby(['Pitcher ID', 'Pitcher Team']):
            player_neutral_stats = calculate_neutral_pitching_stats(player_team_df, re_matrix)
            player_n_ip = player_neutral_stats['nOuts'] / 3
            player_n_runs = player_neutral_stats['nRuns']
            player_n_era = (player_n_runs * 6) / player_n_ip if player_n_ip > 0 else 0
            
            if lg_n_era > 0:
                era_minus = round(100 * (player_n_era / lg_n_era))
            else:
                era_minus = 100
            neutral_pitching_stats.append({'Season': season, 'Pitcher ID': pitcher_id, 'Team': team, 'nIP': player_n_ip, 'ERA-': era_minus, 'nRuns': player_n_runs})

        # Calculate season-total ERA- for all players who were traded
        for pitcher_id, player_df in season_df.groupby('Pitcher ID'):
            teams = player_df['Pitcher Team'].unique()
            if len(teams) > 1:
                player_neutral_stats = calculate_neutral_pitching_stats(player_df, re_matrix)
                player_n_ip = player_neutral_stats['nOuts'] / 3
                player_n_runs = player_neutral_stats['nRuns']
                player_n_era = (player_n_runs * 6) / player_n_ip if player_n_ip > 0 else 0
                
                if lg_n_era > 0:
                    era_minus = round(100 * (player_n_era / lg_n_era))
                else:
                    era_minus = 100
                neutral_pitching_stats.append({'Season': season, 'Pitcher ID': pitcher_id, 'Team': f"{len(teams)}TM", 'nIP': player_n_ip, 'ERA-': era_minus, 'nRuns': player_n_runs})

    neutral_stats_df = pd.DataFrame(neutral_pitching_stats) if neutral_pitching_stats else pd.DataFrame()

    print("Calculating pitching achievements (GS, CG, SHO, GF)...")
    games_started_df = calculate_games_started(combined_df)
    game_achievements_df = calculate_game_achievements(decision_games_df)
    if not game_achievements_df.empty:
        game_achievements_df = pd.merge(games_started_df, game_achievements_df, on=['Season', 'Pitcher ID', 'Team'], how='outer')
    else:
        game_achievements_df = games_started_df

    print("Calculating league-wide stats for OPS+...")
    league_stats_by_season = {}
    for season in leaderboard_df['Season'].unique():
        season_df = leaderboard_df[leaderboard_df['Season'] == season]
        if not season_df.empty:
            league_totals = calculate_hitting_stats(season_df, season=season)
            league_stats_by_season[season] = {'lg_nOBP': league_totals['nOBP'], 'lg_nSLG': league_totals['nSLG']}

    all_seasons_hitting_stats = []
    all_seasons_pitching_stats = []
    all_seasons_team_hitting_stats = []
    all_seasons_team_pitching_stats = []
    for season in sorted_seasons:
        force_recalc = (season == most_recent_season) or (season in seasons_to_recalc)
        season_leaderboard_df = leaderboard_df[leaderboard_df['Season'] == season]

        if player_type_data and season in player_type_data:
            player_types_df = player_type_data[season][['Player ID', 'Batting Type', 'Pitching Type']]
            
            # Merge for hitters
            hitter_types_df = player_types_df.rename(columns={'Player ID': 'Hitter ID', 'Batting Type': 'Hitter Batting Type', 'Pitching Type': 'Hitter Pitching Type'})
            season_leaderboard_df = pd.merge(season_leaderboard_df, hitter_types_df, on='Hitter ID', how='left')
            
            # Merge for pitchers
            pitcher_types_df = player_types_df.rename(columns={'Player ID': 'Pitcher ID', 'Batting Type': 'Pitcher Batting Type', 'Pitching Type': 'Pitcher Pitching Type'})
            season_leaderboard_df = pd.merge(season_leaderboard_df, pitcher_types_df, on='Pitcher ID', how='left')

        hitting_cache_path = os.path.join(cache_dir, f'hitting_stats_{season}.csv')
        pitching_cache_path = os.path.join(cache_dir, f'pitching_stats_{season}.csv')
        team_hitting_cache_path = os.path.join(cache_dir, f'team_hitting_stats_{season}.csv')
        team_pitching_cache_path = os.path.join(cache_dir, f'team_pitching_stats_{season}.csv')

        can_use_cache = False
        if (os.path.exists(hitting_cache_path) and
                os.path.exists(pitching_cache_path) and
                os.path.exists(team_hitting_cache_path) and
                os.path.exists(team_pitching_cache_path) and
                not force_recalc):
            try:
                hitting_cols = pd.read_csv(hitting_cache_path, nrows=0).columns
                pitching_cols = pd.read_csv(pitching_cache_path, nrows=0).columns
                if 'WPA' in hitting_cols and 'BAA' in pitching_cols:
                    can_use_cache = True
            except Exception:
                can_use_cache = False

        if can_use_cache:
            season_hitting_stats = pd.read_csv(hitting_cache_path)
            season_pitching_stats = pd.read_csv(pitching_cache_path)
            season_team_hitting_stats = pd.read_csv(team_hitting_cache_path)
            season_team_pitching_stats = pd.read_csv(team_pitching_cache_path)
        else:
            # --- Hitting Stats Calculation ---
            hitter_records = []
            for (hitter_id), group_df in season_leaderboard_df.groupby('Hitter ID'):
                teams = group_df['Batter Team'].unique()
                
                # Calculate combined stats for the season
                stats_series = calculate_hitting_stats(group_df, season=season)
                if stats_series is not None:
                    stats_series['Season'] = season
                    stats_series['Hitter ID'] = hitter_id
                    stats_series['Team'] = f"{len(teams)}TM" if len(teams) > 1 else teams[0]
                    stats_series['is_sub_row'] = False
                    stats_series['Last Team'] = group_df.sort_values('Session').iloc[-1]['Batter Team']
                    hitter_records.append(stats_series)

                    # If traded, calculate stats for each team
                    if len(teams) > 1:
                        for team in teams:
                            team_df = group_df[group_df['Batter Team'] == team]
                            team_stats_series = calculate_hitting_stats(team_df, season=season)
                            if team_stats_series is not None:
                                team_stats_series['Season'] = season
                                team_stats_series['Hitter ID'] = hitter_id
                                team_stats_series['Team'] = team
                                team_stats_series['is_sub_row'] = True
                                team_stats_series['Last Team'] = team
                                hitter_records.append(team_stats_series)

            season_hitting_stats = pd.DataFrame(hitter_records)

            # --- Pitching Stats Calculation ---
            pitcher_records = []
            for (pitcher_id), group_df in season_leaderboard_df.groupby('Pitcher ID'):
                teams = group_df['Pitcher Team'].unique()

                # Calculate combined stats for the season
                stats_series = calculate_pitching_stats(group_df, season=season)
                if stats_series is not None:
                    stats_series['Season'] = season
                    stats_series['Pitcher ID'] = pitcher_id
                    stats_series['Team'] = f"{len(teams)}TM" if len(teams) > 1 else teams[0]
                    stats_series['is_sub_row'] = False
                    stats_series['Last Team'] = group_df.sort_values('Session').iloc[-1]['Pitcher Team']
                    pitcher_records.append(stats_series)

                    # If traded, calculate stats for each team
                    if len(teams) > 1:
                        for team in teams:
                            team_df = group_df[group_df['Pitcher Team'] == team]
                            team_stats_series = calculate_pitching_stats(team_df, season=season)
                            if team_stats_series is not None:
                                team_stats_series['Season'] = season
                                team_stats_series['Pitcher ID'] = pitcher_id
                                team_stats_series['Team'] = team
                                team_stats_series['is_sub_row'] = True
                                team_stats_series['Last Team'] = team
                                pitcher_records.append(team_stats_series)
            season_pitching_stats = pd.DataFrame(pitcher_records)

            # --- Merge additional pitching stats ---
            if not season_pitching_stats.empty:
                fip_constant = fip_constants_by_season.get(season, 3.10)
                season_pitching_stats['FIP'] = ((13 * season_pitching_stats['HR']) + (3 * season_pitching_stats['BB']) - (2 * season_pitching_stats['K'])) / season_pitching_stats['IP'] + fip_constant
                season_neutral_stats = neutral_stats_df[neutral_stats_df['Season'] == season] if not neutral_stats_df.empty else pd.DataFrame()
                season_achievements = game_achievements_df[game_achievements_df['Season'] == season]
                season_decisions = regular_pitcher_stats_agg[regular_pitcher_stats_agg['Season'] == season]

                if not season_neutral_stats.empty:
                    season_pitching_stats = season_pitching_stats.merge(season_neutral_stats, on=['Season', 'Pitcher ID', 'Team'], how='left')
                if not season_achievements.empty:
                    season_pitching_stats = season_pitching_stats.merge(season_achievements, on=['Season', 'Pitcher ID', 'Team'], how='left')
                if not season_decisions.empty: 
                    season_pitching_stats = season_pitching_stats.merge(season_decisions, on=['Season', 'Pitcher ID', 'Team'], how='left')

                stats_to_sum = ['W', 'L', 'SV', 'HLD', 'GS', 'GF', 'CG', 'SHO']
                for col in stats_to_sum:
                    if col not in season_pitching_stats.columns:
                        season_pitching_stats[col] = 0
                season_pitching_stats[stats_to_sum] = season_pitching_stats[stats_to_sum].fillna(0)

                traded_player_ids = season_pitching_stats[season_pitching_stats['is_sub_row'] == True]['Pitcher ID'].unique()
                for pid in traded_player_ids:
                    player_mask = season_pitching_stats['Pitcher ID'] == pid
                    total_row_idx = season_pitching_stats.index[player_mask & (season_pitching_stats['is_sub_row'] == False)]
                    if len(total_row_idx) > 0:
                        team_rows = season_pitching_stats[player_mask & (season_pitching_stats['is_sub_row'] == True)]
                        season_pitching_stats.loc[total_row_idx, stats_to_sum] = team_rows[stats_to_sum].sum().values

                if 'W' in season_pitching_stats.columns and 'L' in season_pitching_stats.columns:
                    season_pitching_stats['W-L%'] = (season_pitching_stats['W'] / (season_pitching_stats['W'] + season_pitching_stats['L'])).fillna(0)

            # --- WAR Calculation ---
            if not season_hitting_stats.empty and not season_pitching_stats.empty:
                # WAR is based on the total number of games played in a season.
                num_total_games = season_leaderboard_df['Game ID'].nunique()

                if num_total_games > 0:
                    # The league generates 0.41 WAR per game, so we use that as our constant.
                    total_war_season = num_total_games * 0.41
                    runs_per_win = 10
                    total_rar_season = total_war_season * runs_per_win

                    # Hitting WAR
                    total_pa_season = season_hitting_stats['PA'].sum()
                    if total_pa_season > 0:
                        total_rar_h = total_rar_season / 2
                        runs_per_pa_replacement_h = total_rar_h / total_pa_season
                        season_hitting_stats['WAR'] = (season_hitting_stats['RE24'] + runs_per_pa_replacement_h * season_hitting_stats['PA']) / runs_per_win
                    else:
                        season_hitting_stats['WAR'] = 0

                    # Pitching WAR
                    total_bf_season = season_pitching_stats['BF'].sum()
                    if total_bf_season > 0:
                        total_rar_p = total_rar_season / 2
                        runs_per_bf_replacement_p = total_rar_p / total_bf_season
                        season_pitching_stats['WAR'] = (-season_pitching_stats['RE24'] + runs_per_bf_replacement_p * season_pitching_stats['BF']) / runs_per_win
                    else:
                        season_pitching_stats['WAR'] = 0
                else:
                    season_hitting_stats['WAR'] = 0
                    season_pitching_stats['WAR'] = 0
            
            # --- Cache Results ---
            if not season_hitting_stats.empty:
                season_hitting_stats.to_csv(hitting_cache_path, index=False)
            if not season_pitching_stats.empty:
                season_pitching_stats.to_csv(pitching_cache_path, index=False)

            # --- Team Hitting Stats Calculation ---
            team_hitting_records = []
            if not season_hitting_stats.empty:
                source_hitting_df = season_hitting_stats[~season_hitting_stats['Team'].str.contains("TM")].copy()
                league_stats_for_season = league_stats_by_season.get(season)
                for team, team_df in source_hitting_df.groupby('Team'):
                    team_stats_series = calculate_team_hitting_stats(team_df, league_stats_for_season)
                    team_stats_series['Season'] = season
                    team_stats_series['Team'] = team
                    team_hitting_records.append(team_stats_series)
            season_team_hitting_stats = pd.DataFrame(team_hitting_records)
            if not season_team_hitting_stats.empty:
                team_games = season_leaderboard_df.groupby('Batter Team')['Session'].nunique()
                season_team_hitting_stats['G'] = season_team_hitting_stats['Team'].map(team_games)

            # --- Team Pitching Stats Calculation ---
            team_pitching_records = []
            if not season_pitching_stats.empty:
                source_pitching_df = season_pitching_stats[~season_pitching_stats['Team'].str.contains("TM")].copy()
                league_n_era_for_season = league_n_era_by_season.get(season, 0)
                fip_constant_for_season = fip_constants_by_season.get(season, 3.10)

                season_team_neutral_pitching_stats = {}
                re_matrix = run_expectancy_by_season.get(season, {})
                if re_matrix:
                    for team, team_df in season_leaderboard_df.groupby('Pitcher Team'):
                        neutral_stats = calculate_neutral_pitching_stats(team_df, re_matrix)
                        n_ip = neutral_stats['nOuts'] / 3
                        n_era = (neutral_stats['nRuns'] * 6) / n_ip if n_ip > 0 else 0
                        season_team_neutral_pitching_stats[team] = n_era
                
                for team, team_df in source_pitching_df.groupby('Team'):
                    team_n_era = season_team_neutral_pitching_stats.get(team, 0)
                    team_stats_series = calculate_team_pitching_stats(team_df, league_n_era_for_season, team_n_era, fip_constant_for_season)
                    team_stats_series['Season'] = season
                    team_stats_series['Team'] = team
                    team_pitching_records.append(team_stats_series)
            season_team_pitching_stats = pd.DataFrame(team_pitching_records)

            # --- Cache Team Stats ---
            if not season_team_hitting_stats.empty:
                season_team_hitting_stats.to_csv(team_hitting_cache_path, index=False)
            if not season_team_pitching_stats.empty:
                season_team_pitching_stats.to_csv(team_pitching_cache_path, index=False)

        all_seasons_hitting_stats.append(season_hitting_stats)
        all_seasons_pitching_stats.append(season_pitching_stats)
        all_seasons_team_hitting_stats.append(season_team_hitting_stats)
        all_seasons_team_pitching_stats.append(season_team_pitching_stats)

    # --- Final Assembly ---
    all_hitting_stats = pd.concat(all_seasons_hitting_stats, ignore_index=True)
    all_pitching_stats = pd.concat(all_seasons_pitching_stats, ignore_index=True)

    print("Applying post-processing corrections...")
    all_pitching_stats = apply_postprocessing_corrections(all_pitching_stats)

    all_team_hitting_stats = pd.concat(all_seasons_team_hitting_stats, ignore_index=True)

    print("Recalculating team pitching stats with corrected data...")
    team_pitching_records = []
    # Use the seasons from the original sorted list to maintain order and completeness
    for season in sorted_seasons:
        season_pitching_stats = all_pitching_stats[all_pitching_stats['Season'] == season]
        if season_pitching_stats.empty:
            continue

        # Dependencies for calculate_team_pitching_stats
        league_n_era_for_season = league_n_era_by_season.get(season, 0)
        fip_constant_for_season = fip_constants_by_season.get(season, 3.10)
        
        # Recalculate team neutral ERA for the season
        season_leaderboard_df = leaderboard_df[leaderboard_df['Season'] == season]
        season_team_neutral_pitching_stats = {}
        re_matrix = run_expectancy_by_season.get(season, {})
        if re_matrix:
            # Check if 'Pitcher Team' exists and is not empty to avoid errors on empty df
            if 'Pitcher Team' in season_leaderboard_df.columns and not season_leaderboard_df['Pitcher Team'].dropna().empty:
                for team, team_df in season_leaderboard_df.groupby('Pitcher Team'):
                    neutral_stats = calculate_neutral_pitching_stats(team_df, re_matrix)
                    n_ip = neutral_stats['nOuts'] / 3
                    n_era = (neutral_stats['nRuns'] * 6) / n_ip if n_ip > 0 else 0
                    season_team_neutral_pitching_stats[team] = n_era
        
        # Get the source data for team aggregation
        source_pitching_df = season_pitching_stats[~season_pitching_stats['Team'].str.contains("TM")].copy()
        
        if not source_pitching_df.empty:
            for team, team_df in source_pitching_df.groupby('Team'):
                team_n_era = season_team_neutral_pitching_stats.get(team, 0)
                team_stats_series = calculate_team_pitching_stats(team_df, league_n_era_for_season, team_n_era, fip_constant_for_season)
                team_stats_series['Season'] = season
                team_stats_series['Team'] = team
                team_pitching_records.append(team_stats_series)
            
    if team_pitching_records:
        all_team_pitching_stats = pd.DataFrame(team_pitching_records)
    else:
        # Fallback to the old (uncorrected) data if something went wrong
        all_team_pitching_stats = pd.concat(all_seasons_team_pitching_stats, ignore_index=True)

    if not all_hitting_stats.empty:
        all_hitting_stats['OPS+'] = all_hitting_stats.apply(calculate_ops_plus_for_row, axis=1, league_stats_by_season=league_stats_by_season)

    # --- Career Stats Calculation ---
    print("Calculating career stats...")
    # Hitting
    career_hitting_stats = all_hitting_stats[all_hitting_stats['is_sub_row'] == False].groupby('Hitter ID').apply(lambda df: calculate_career_hitting_stats(df, league_stats_by_season), include_groups=False).reset_index()
    career_hitting_stats['Season'] = 'Career'
    all_hitting_stats = pd.concat([all_hitting_stats, career_hitting_stats], ignore_index=True)

    # Pitching
    career_pitching_stats = all_pitching_stats[all_pitching_stats['is_sub_row'] == False].groupby('Pitcher ID').apply(lambda df: calculate_career_pitching_stats(df, league_n_era_by_season), include_groups=False).reset_index()
    career_pitching_stats['Season'] = 'Career'
    all_pitching_stats = pd.concat([all_pitching_stats, career_pitching_stats], ignore_index=True)
    print("Career stats calculated.")

    # --- Franchise Totals Calculation ---
    print("Calculating franchise totals...")
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'data')
    team_history_path = os.path.join(output_dir, 'team_history.json')
    try:
        with open(team_history_path, 'r') as f:
            team_history = json.load(f)
    except FileNotFoundError:
        print("Warning: team_history.json not found. Cannot calculate franchise totals.")
        team_history = {}

    abbr_to_franchise = {}
    if team_history:
        for franchise_key, entries in team_history.items():
            for entry in entries:
                end_season = 9999 if entry['end'] == 'current' or entry['end'] == float('inf') else entry['end']
                for season_num in range(entry['start'], end_season + 1):
                    abbr_to_franchise[(entry['abbr'], season_num)] = franchise_key
    
    # Hitting
    if not all_hitting_stats.empty and abbr_to_franchise:
        franchise_source_hitting = all_hitting_stats[
            (all_hitting_stats['Season'] != 'Career') &
            ((all_hitting_stats['is_sub_row'] == True) | (~all_hitting_stats['Team'].str.contains("TM", na=False)))
        ].copy()

        franchise_source_hitting['franchise'] = franchise_source_hitting.apply(
            lambda row: abbr_to_franchise.get((row['Team'], int(row['Season'].replace('S','')))),
            axis=1
        )

        franchise_hitting_stats = franchise_source_hitting.dropna(subset=['franchise']).groupby(['Hitter ID', 'franchise']).apply(
            lambda df: calculate_career_hitting_stats(df, league_stats_by_season), include_groups=False
        ).reset_index()

        if not franchise_hitting_stats.empty:
            franchise_hitting_stats.rename(columns={'franchise': 'Team'}, inplace=True)
            franchise_hitting_stats['Season'] = 'Franchise'
            all_hitting_stats = pd.concat([all_hitting_stats, franchise_hitting_stats], ignore_index=True)

    # Pitching
    if not all_pitching_stats.empty and abbr_to_franchise:
        franchise_source_pitching = all_pitching_stats[
            (all_pitching_stats['Season'] != 'Career') &
            ((all_pitching_stats['is_sub_row'] == True) | (~all_pitching_stats['Team'].str.contains("TM", na=False)))
        ].copy()

        franchise_source_pitching['franchise'] = franchise_source_pitching.apply(
            lambda row: abbr_to_franchise.get((row['Team'], int(row['Season'].replace('S','')))),
            axis=1
        )

        franchise_pitching_stats = franchise_source_pitching.dropna(subset=['franchise']).groupby(['Pitcher ID', 'franchise']).apply(
            lambda df: calculate_career_pitching_stats(df, league_n_era_by_season), include_groups=False
        ).reset_index()

        if not franchise_pitching_stats.empty:
            franchise_pitching_stats.rename(columns={'franchise': 'Team'}, inplace=True)
            franchise_pitching_stats['Season'] = 'Franchise'
            all_pitching_stats = pd.concat([all_pitching_stats, franchise_pitching_stats], ignore_index=True)
    
    print("Franchise totals calculated.")

    # --- Type Totals Calculation ---
    print("Calculating type totals...")
    # Hitting
    if not all_hitting_stats.empty:
        type_source_hitting = all_hitting_stats[
            (all_hitting_stats['Season'].str.startswith('S')) &
            (all_hitting_stats['is_sub_row'] == False)
        ].copy()

        type_source_hitting.dropna(subset=['Type'], inplace=True)

        type_hitting_stats = type_source_hitting.groupby(['Hitter ID', 'Type']).apply(
            lambda df: calculate_career_hitting_stats(df, league_stats_by_season, include_type_column=False), include_groups=False
        ).reset_index()

        if not type_hitting_stats.empty:
            type_hitting_stats['Season'] = 'Type'
            all_hitting_stats = pd.concat([all_hitting_stats, type_hitting_stats], ignore_index=True)

    # Pitching
    if not all_pitching_stats.empty:
        type_source_pitching = all_pitching_stats[
            (all_pitching_stats['Season'].str.startswith('S')) &
            (all_pitching_stats['is_sub_row'] == False)
        ].copy()

        type_source_pitching.dropna(subset=['Type'], inplace=True)
        type_source_pitching['Main Type'] = type_source_pitching['Type'].str.split('-').str[0]

        type_pitching_stats = type_source_pitching.groupby(['Pitcher ID', 'Main Type']).apply(
            lambda df: calculate_career_pitching_stats(df, league_n_era_by_season, include_type_column=False), include_groups=False
        ).reset_index()

        if not type_pitching_stats.empty:
            type_pitching_stats.rename(columns={'Main Type': 'Type'}, inplace=True)
            type_pitching_stats['Season'] = 'Type'
            all_pitching_stats = pd.concat([all_pitching_stats, type_pitching_stats], ignore_index=True)
    
    print("Type totals calculated.")


    # --- Update Glossary with RE Matrix ---
    print("Updating glossary with RE Matrix...")
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'data')
    glossary_path = os.path.join(output_dir, 'glossary.json')
    try:
        with open(glossary_path, 'r') as f:
            glossary_data = json.load(f)

        if most_recent_season:
            season_num = int(most_recent_season.replace('S', ''))
            re_matrix_section = generate_re_matrix_html(season_num)
            
            if re_matrix_section and 'RE24' in glossary_data:
                # Remove old matrix if it exists to prevent duplicates
                glossary_data['RE24']['sections'] = [s for s in glossary_data['RE24']['sections'] if "Run Expectancy Matrix" not in s['title']]
                # Add the new one
                glossary_data['RE24']['sections'].append(re_matrix_section)
                
                with open(glossary_path, 'w') as f:
                    json.dump(glossary_data, f, indent=4)
                print("Glossary updated successfully.")

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not update glossary.json. Error: {e}")


    _write_cache_manifest(cache_dir, most_recent_season)
    print("Calculations complete.")

    # --- EXPORTING DATA ---
    print("Exporting data for web app...")
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'data')
    if not os.path.exists(output_dir): os.makedirs(output_dir)

    # Save current season info
    max_session = 0
    if most_recent_season:
        most_recent_season_df = combined_df[combined_df['Season'] == most_recent_season]
        if not most_recent_season_df.empty:
            max_session = most_recent_season_df['Session'].max()
    current_season_info = {
        'season': most_recent_season if most_recent_season else None,
        'session': int(max_session) if max_session > 0 else 1
    }
    with open(os.path.join(output_dir, 'current_season_info.json'), 'w') as f:
        json.dump(current_season_info, f, indent=2)

    # Save player ID map
    with open(os.path.join(output_dir, 'player_id_map.json'), 'w') as f:
        json.dump(player_id_map, f, indent=4)

    # Save main stats
    all_hitting_stats.replace([float('inf'), float('-inf')], None, inplace=True)
    all_hitting_stats = all_hitting_stats.astype(object).where(pd.notna(all_hitting_stats), None)
    hitting_data = {
        "columns": all_hitting_stats.columns.tolist(),
        "data": all_hitting_stats.values.tolist()
    }
    with open(os.path.join(output_dir, 'hitting_stats.json'), 'w') as f:
        json.dump(hitting_data, f, indent=2)

    all_pitching_stats.to_json(os.path.join(output_dir, 'pitching_stats.json'), orient='split', index=False)

    if not all_team_hitting_stats.empty:
        all_team_hitting_stats_for_json = all_team_hitting_stats.copy()
        for col in all_team_hitting_stats_for_json.columns:
            if all_team_hitting_stats_for_json[col].dtype == 'float64':
                all_team_hitting_stats_for_json[col] = all_team_hitting_stats_for_json[col].round(3)
        all_team_hitting_stats_for_json.to_json(os.path.join(output_dir, 'team_hitting_stats.json'), orient='split', index=False)

    if not all_team_pitching_stats.empty:
        all_team_pitching_stats_for_json = all_team_pitching_stats.copy()
        if 'IP' in all_team_pitching_stats_for_json.columns:
            all_team_pitching_stats_for_json['IP'] = all_team_pitching_stats_for_json['IP'].apply(format_ip)
        for col in all_team_pitching_stats_for_json.columns:
            if all_team_pitching_stats_for_json[col].dtype == 'float64':
                all_team_pitching_stats_for_json[col] = all_team_pitching_stats_for_json[col].round(3)
        all_team_pitching_stats_for_json.to_json(os.path.join(output_dir, 'team_pitching_stats.json'), orient='split', index=False)

    # --- Scouting Reports ---
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

    print("Done!")

if __name__ == "__main__":
    main()