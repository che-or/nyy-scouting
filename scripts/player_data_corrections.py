import pandas as pd

def _recalculate_wl_pct(df, mask):
    """Recalculates W-L% for the rows matching the mask."""
    wins = df.loc[mask, 'W']
    losses = df.loc[mask, 'L']
    total_games = wins + losses
    # .fillna(0) handles division by zero if total_games is 0
    df.loc[mask, 'W-L%'] = (wins / total_games).fillna(0)

def apply_postprocessing_corrections(player_stats_df):
    """
    Applies manual post-processing corrections to aggregated player statistics.

    This is intended for cases where data errors (like a pitcher appearing for two teams
    in the same game) are not caught during initial gamelog processing and need to be
    fixed in the final aggregated data.

    Args:
        player_stats_df (pd.DataFrame): The DataFrame containing aggregated player stats
                                        (e.g., all_pitching_stats from generate_web_data.py).

    Returns:
        pd.DataFrame: The corrected DataFrame.
    
    Note:
        Applying corrections at this stage can be complex. For example, if you
        merge stats for a player who appeared under two teams, you will likely need
        to recalculate all rate stats (ERA, WHIP, BAA, etc.) for the new combined row.
        Correcting the raw gamelog data *before* aggregation is often a simpler approach.
    """

    # Add specific player corrections here.
    # For example, to merge a player's stats from a secondary team to a primary team:
    #
    # pitcher_id = 123
    # season = 'S2'
    # primary_team = 'TEX'
    # secondary_team = 'HOU'
    #
    # # Locate the rows
    # primary_mask = (player_stats_df['Pitcher ID'] == pitcher_id) & (player_stats_df['Season'] == season) & (player_stats_df['Team'] == primary_team)
    # secondary_mask = (player_stats_df['Pitcher ID'] == pitcher_id) & (player_stats_df['Season'] == season) & (player_stats_df['Team'] == secondary_team)
    #
    # if player_stats_df[primary_mask].shape[0] > 0 and player_stats_df[secondary_mask].shape[0] > 0:
    #     # Get indices
    #     primary_idx = player_stats_df[primary_mask].index[0]
    #     secondary_idx = player_stats_df[secondary_mask].index[0]
    #
    #     # Sum countable stats
    #     countable_stats = ['G', 'IP', 'BF', 'H', 'R', 'ER', 'BB', 'K', 'HR', 'W', 'L', 'SV', 'HLD']
    #     for stat in countable_stats:
    #         if stat in player_stats_df.columns:
    #             player_stats_df.loc[primary_idx, stat] += player_stats_df.loc[secondary_idx, stat]
    #
    #     # Drop the merged row
    #     player_stats_df.drop(secondary_idx, inplace=True)
    #
    #     # At this point, rate stats for the modified row are incorrect and would need to be recalculated.

    # S1, Player 237, BAL: -1 L
    s1_p237_mask = (player_stats_df['Season'] == 'S1') &                   (player_stats_df['Pitcher ID'] == 237) &                    (player_stats_df['Team'] == 'BAL')
    if not player_stats_df[s1_p237_mask].empty:
        player_stats_df.loc[s1_p237_mask, 'L'] -= 1
        _recalculate_wl_pct(player_stats_df, s1_p237_mask)

        total_mask = (player_stats_df['Season'] == 'S1') & (player_stats_df['Pitcher ID'] == 237) & (player_stats_df['is_sub_row'] == False)
        if not player_stats_df[total_mask].empty:
            player_stats_df.loc[total_mask, 'L'] -= 1
            _recalculate_wl_pct(player_stats_df, total_mask)

    # S2, Player 373, BAL: -1 W
    s2_p373_mask = (player_stats_df['Season'] == 'S2') &                   (player_stats_df['Pitcher ID'] == 373) &                   (player_stats_df['Team'] == 'BAL')
    if not player_stats_df[s2_p373_mask].empty:
        player_stats_df.loc[s2_p373_mask, 'W'] -= 1
        _recalculate_wl_pct(player_stats_df, s2_p373_mask)

        total_mask = (player_stats_df['Season'] == 'S2') & (player_stats_df['Pitcher ID'] == 373) & (player_stats_df['is_sub_row'] == False)
        if not player_stats_df[total_mask].empty:
            player_stats_df.loc[total_mask, 'W'] -= 1
            _recalculate_wl_pct(player_stats_df, total_mask)

    # S3, Player 321, ARI: -1 W
    s3_p321_mask = (player_stats_df['Season'] == 'S3') &                   (player_stats_df['Pitcher ID'] == 321) &                   (player_stats_df['Team'] == 'ARI')
    if not player_stats_df[s3_p321_mask].empty:
        player_stats_df.loc[s3_p321_mask, 'W'] -= 1
        _recalculate_wl_pct(player_stats_df, s3_p321_mask)

        total_mask = (player_stats_df['Season'] == 'S3') & (player_stats_df['Pitcher ID'] == 321) & (player_stats_df['is_sub_row'] == False)
        if not player_stats_df[total_mask].empty:
            player_stats_df.loc[total_mask, 'W'] -= 1
            _recalculate_wl_pct(player_stats_df, total_mask)

    # S3, Player 269, OAK: +1 L, -1 W
    s3_p269_mask = (player_stats_df['Season'] == 'S3') &                   (player_stats_df['Pitcher ID'] == 269) &                   (player_stats_df['Team'] == 'OAK')
    if not player_stats_df[s3_p269_mask].empty:
        player_stats_df.loc[s3_p269_mask, 'L'] += 1
        player_stats_df.loc[s3_p269_mask, 'W'] -= 1
        _recalculate_wl_pct(player_stats_df, s3_p269_mask)

        total_mask = (player_stats_df['Season'] == 'S3') & (player_stats_df['Pitcher ID'] == 269) & (player_stats_df['is_sub_row'] == False)
        if not player_stats_df[total_mask].empty:
            player_stats_df.loc[total_mask, 'L'] += 1
            player_stats_df.loc[total_mask, 'W'] -= 1
            _recalculate_wl_pct(player_stats_df, total_mask)

    # S2, Player 2151, WSH: -1 W, +1 L
    s2_p2151_mask = (player_stats_df['Season'] == 'S2') & \
                   (player_stats_df['Pitcher ID'] == 2151) & \
                   (player_stats_df['Team'] == 'WSH')
    if not player_stats_df[s2_p2151_mask].empty:
        player_stats_df.loc[s2_p2151_mask, 'W'] -= 1
        player_stats_df.loc[s2_p2151_mask, 'L'] += 1
        _recalculate_wl_pct(player_stats_df, s2_p2151_mask)

        # If this was a sub-row, we also need to correct the total row.
        is_sub_row = player_stats_df.loc[s2_p2151_mask, 'is_sub_row'].iloc[0]
        if is_sub_row:
            total_mask = (player_stats_df['Season'] == 'S2') & \
                         (player_stats_df['Pitcher ID'] == 2151) & \
                         (player_stats_df['is_sub_row'] == False)
            if not player_stats_df[total_mask].empty:
                player_stats_df.loc[total_mask, 'W'] -= 1
                player_stats_df.loc[total_mask, 'L'] += 1
                _recalculate_wl_pct(player_stats_df, total_mask)

    # S2, Player 1997, SDP: +1 W
    s2_p1997_mask = (player_stats_df['Season'] == 'S2') & \
                   (player_stats_df['Pitcher ID'] == 1997) & \
                   (player_stats_df['Team'] == 'SDP')
    if not player_stats_df[s2_p1997_mask].empty:
        player_stats_df.loc[s2_p1997_mask, 'W'] += 1
        _recalculate_wl_pct(player_stats_df, s2_p1997_mask)

        is_sub_row = player_stats_df.loc[s2_p1997_mask, 'is_sub_row'].iloc[0]
        if is_sub_row:
            total_mask = (player_stats_df['Season'] == 'S2') & \
                         (player_stats_df['Pitcher ID'] == 1997) & \
                         (player_stats_df['is_sub_row'] == False)
            if not player_stats_df[total_mask].empty:
                player_stats_df.loc[total_mask, 'W'] += 1
                _recalculate_wl_pct(player_stats_df, total_mask)

    # S2, Player 2031, SDP: -1 L
    s2_p2031_mask = (player_stats_df['Season'] == 'S2') & \
                   (player_stats_df['Pitcher ID'] == 2031) & \
                   (player_stats_df['Team'] == 'SDP')
    if not player_stats_df[s2_p2031_mask].empty:
        player_stats_df.loc[s2_p2031_mask, 'L'] -= 1
        _recalculate_wl_pct(player_stats_df, s2_p2031_mask)

        is_sub_row = player_stats_df.loc[s2_p2031_mask, 'is_sub_row'].iloc[0]
        if is_sub_row:
            total_mask = (player_stats_df['Season'] == 'S2') & \
                         (player_stats_df['Pitcher ID'] == 2031) & \
                         (player_stats_df['is_sub_row'] == False)
            if not player_stats_df[total_mask].empty:
                player_stats_df.loc[total_mask, 'L'] -= 1
                _recalculate_wl_pct(player_stats_df, total_mask)

    return player_stats_df
