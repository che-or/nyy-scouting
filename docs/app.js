document.addEventListener('DOMContentLoaded', () => {
    const API = {
        hitting: './data/hitting_stats.json',
        pitching: './data/pitching_stats.json',
        players: './data/player_id_map.json',
        seasons: './data/season_games_map.json',
        scouting: './data/scouting_reports.json',
        glossary: './data/glossary.json',
        divisions: './data/divisions.json', // Added
        teamHistory: './data/team_history.json',
        teamHitting: './data/team_hitting_stats.json',
        teamPitching: './data/team_pitching_stats.json',
        gamelogErrors: './data/gamelog-errors.json',
        typeDefinitions: './data/type_definitions.json',
        playerInfo: './data/player_info.json',
        currentSeasonInfo: './data/current_season_info.json'
    };

    const state = {
        hittingStats: [],
        pitchingStats: [],
        teamHittingStats: [],
        teamPitchingStats: [],
        players: {},
        seasons: {},
        scoutingReports: {},
        glossaryData: {},
        divisions: {}, // Added,
        teamHistory: {},
        gamelogErrors: [],
        typeDefinitions: {},
        playerInfo: {},
        currentSeasonInfo: {},
        playerMap: new Map(),
        currentPlayerId: null,
        lastTeamStatsUrl: '#/team-stats',
        seasonsWithStats: []
    };

    const elements = {
        loader: document.getElementById('loader'),
        app: document.getElementById('app'),
        
        homeView: document.getElementById('home-view'),
        statsView: document.getElementById('stats-view'),
        leaderboardsView: document.getElementById('leaderboards-view'),
        glossaryView: document.getElementById('glossary-view'),
        teamStatsView: document.getElementById('team-stats-view'),
        
        homeTab: document.getElementById('home-tab'),
        statsTab: document.getElementById('stats-tab'),
        teamStatsTab: document.getElementById('team-stats-tab'),
        leaderboardsTab: document.getElementById('leaderboards-tab'),
        glossaryTab: document.getElementById('glossary-tab'),

        playerSearch: document.getElementById('player-search'),
        playerSuggestions: document.getElementById('player-suggestions'),
        statsContentDisplay: document.getElementById('stats-content-display'),

        leaderboardTypeSelect: document.getElementById('leaderboard-type-select'),
        leaderboardStatSelect: document.getElementById('leaderboard-stat-select'),
        leaderboardButton: document.getElementById('leaderboard-button'),
        leaderboardLength: document.getElementById('leaderboard-length'),
        leaderboardTeamFilter: document.getElementById('leaderboard-team-filter'),
        leaderboardTypeFilter: document.getElementById('leaderboard-type-filter'),
        reverseSort: document.getElementById('reverse-sort'),
        leaderboardsContentDisplay: document.getElementById('leaderboards-content-display'),
        minPa: document.getElementById('min-pa'),
        minOuts: document.getElementById('min-outs'),
        battingMinimumControls: document.getElementById('batting-minimum-controls'),
        pitchingMinimumControls: document.getElementById('pitching-minimum-controls'),
        attemptsMinimumControls: document.getElementById('attempts-minimum-controls'),
        decisionsMinimumControls: document.getElementById('decisions-minimum-controls'),
        minPaLabel: document.querySelector('label[for="min-pa"]'),
        minOutsLabel: document.querySelector('label[for="min-outs"]'),
        minAttempts: document.getElementById('min-attempts'),
        minDecisions: document.getElementById('min-decisions'),
        themeSwitch: document.getElementById('theme-switch-input')
    };

    const COUNTING_STATS = ['G', 'PA', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'IBB', 'SO', 'Auto K', 'TB', 'GIDP', 'SH', 'SF', 'W', 'L', 'GS', 'GF', 'CG', 'SHO', 'SV', 'HLD', 'IP', 'ER', 'Auto BB', 'AUTO BB', 'BF', '1B', 'RGO', 'LGO', 'GO', 'FO', 'PO', 'LO', 'WAR', 'WPA', 'RE24'];

    const handleStatSelectChange = () => {
        const stat = elements.leaderboardStatSelect.value;
        const isCounting = COUNTING_STATS.includes(stat);

        // Hide all minimum controls by default
        elements.battingMinimumControls.style.display = 'none';
        elements.pitchingMinimumControls.style.display = 'none';
        elements.attemptsMinimumControls.style.display = 'none';
        elements.decisionsMinimumControls.style.display = 'none';
        
        elements.minPa.classList.add('disabled-input');
        elements.minPaLabel.classList.add('disabled-input');
        elements.minOuts.classList.add('disabled-input');
        elements.minOutsLabel.classList.add('disabled-input');

        if (stat === 'SB%') {
            elements.attemptsMinimumControls.style.display = 'inline-block';
        } else if (stat === 'W-L%') {
            elements.decisionsMinimumControls.style.display = 'inline-block';
        } else if (!isCounting) {
            const type = elements.leaderboardTypeSelect.value;
            if (type === 'batting') {
                elements.battingMinimumControls.style.display = 'inline-block';
                elements.minPa.classList.remove('disabled-input');
                elements.minPaLabel.classList.remove('disabled-input');
            } else {
                elements.pitchingMinimumControls.style.display = 'inline-block';
                elements.minOuts.classList.remove('disabled-input');
                elements.minOutsLabel.classList.remove('disabled-input');
            }
        }
    };

    const parseCompactData = (response) => {
        const { columns, data } = response;
        return data.map(row => {
            const obj = {};
            columns.forEach((col, i) => {
                obj[col] = row[i];
            });
            return obj;
        });
    };

    const STAT_DEFINITIONS = {
        batting_tables: {
            'Standard Batting': ['Season', 'Team', 'Type', 'WAR', 'G', 'PA', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'IBB', 'SO', 'Auto K', 'BA', 'OBP', 'SLG', 'OPS', 'OPS+'],
            'Advanced Batting': ['Season', 'Team', 'TB', 'GIDP', 'SH', 'SF', 'BABIP', 'ISO', 'HR%', 'SO%', 'BB%', 'GB%', 'FB%', 'GB/FB', 'WPA', 'RE24', 'SB%', 'Avg Diff']
        },
        pitching_tables: {
            'Standard Pitching': ['Season', 'Team', 'Type', 'WAR', 'W', 'L', 'W-L%', 'ERA', 'G', 'GS', 'GF', 'CG', 'SHO', 'SV', 'HLD', 'IP', 'H', 'ER', 'HR', 'BB', 'IBB', 'Auto BB', 'SO', 'BF', 'ERA-'],
            'Advanced Pitching': ['Season', 'Team', 'FIP', 'WHIP', 'H6', 'HR6', 'BB6', 'SO6', 'SO/BB', 'HR%', 'K%', 'BB%', 'GB%', 'FB%', 'GB/FB', 'WPA', 'RE24', 'Avg Diff'],
            'Opponent Stats': ['Season', 'Team', 'BA', 'OBP', 'SLG', 'OPS', 'BABIP', 'SB', 'CS', 'SB%']
        }
    };

    const STAT_DESCRIPTIONS = {
        'WAR': 'Wins Above Replacement',
        'G': 'Games Played',
        'PA': 'Plate Appearances',
        'AB': 'At Bats',
        'R': 'Runs Scored',
        'H': 'Hits',
        '2B': 'Doubles',
        '3B': 'Triples',
        'HR': 'Home Runs',
        'RBI': 'Runs Batted In',
        'SB': 'Stolen Bases',
        'CS': 'Caught Stealing',
        'BB': 'Walks (Bases on Balls)',
        'IBB': 'Intentional Walks',
        'SO': 'Strikeouts',
        'Auto K': 'Automatic Strikeouts',
        'BA': 'Batting Average',
        'OBP': 'On-base Percentage',
        'SLG': 'Slugging Percentage',
        'OPS': 'On-base Plus Slugging',
        'OPS+': 'OPS adjusted for park and league',
        'TB': 'Total Bases',
        'GIDP': 'Grounded Into Double Play',
        'SH': 'Sacrifice Hits (Bunts)',
        'SF': 'Sacrifice Flies',
        'BABIP': 'Batting Average on Balls In Play',
        'ISO': 'Isolated Power',
        'HR%': 'Home Run Percentage',
        'SO%': 'Strikeout Percentage',
        'BB%': 'Walk Percentage',
        'GB%': 'Ground Ball Percentage',
        'FB%': 'Fly Ball Percentage',
        'GB/FB': 'Ground Ball to Fly Ball Ratio',
        'WPA': 'Win Probability Added',
        'RE24': 'Run Expectancy based on 24 base-out states',
        'SB%': 'Stolen Base Percentage',
        'Avg Diff': 'Average Difference',
        'W': 'Wins',
        'L': 'Losses',
        'W-L%': 'Win-Loss Percentage',
        'ERA': 'Earned Run Average',
        'GS': 'Games Started',
        'GF': 'Games Finished',
        'CG': 'Complete Games',
        'SHO': 'Shutouts',
        'SV': 'Saves',
        'HLD': 'Holds',
        'IP': 'Innings Pitched',
        'ER': 'Earned Runs',
        'Auto BB': 'Automatic Walks',
        'BF': 'Batters Faced',
        'ERA-': 'ERA Minus - ERA adjusted for park and league, where 100 is average and lower is better',
        'FIP': 'Fielding Independent Pitching',
        'WHIP': 'Walks + Hits per Inning Pitched',
        'H6': 'Hits per 6 Innings',
        'HR6': 'Home Runs per 6 Innings',
        'BB6': 'Walks per 6 Innings',
        'SO6': 'Strikeouts per 6 Innings',
        'SO/BB': 'Strikeout to Walk Ratio',
        'K%': 'Strikeout Percentage',
    };

    const GLOSSARY_GROUPS = {
        "General": ["WAR", "WPA", "RE24"],
        "Batting": ["BA", "OBP", "SLG", "OPS", "ISO", "BABIP", "OPS+"],
        "Pitching": ["W", "L", "SV", "HLD", "ERA", "WHIP", "FIP", "ERA-"]
    };

    const LEADERBOARD_ONLY_STATS = {
        hitting: ['1B', 'RGO', 'LGO', 'GO', 'FO', 'PO', 'LO'],
        pitching: ['1B', '2B', '3B', 'RGO', 'LGO', 'GO', 'FO', 'PO', 'LO']
    };




    const loadData = async () => {
        try {
            const [hitting, pitching, players, seasons, scouting, glossary, divisions, teamHistory, teamHitting, teamPitching, gamelogErrors, typeDefinitions, playerInfo, currentSeasonInfo] = await Promise.all([
                fetch(API.hitting).then(res => res.json()),
                fetch(API.pitching).then(res => res.json()),
                fetch(API.players).then(res => res.json()),
                fetch(API.seasons).then(res => res.json()),
                fetch(API.scouting).then(res => res.json()),
                fetch(API.glossary).then(res => res.json()),
                fetch(API.divisions).then(res => res.json()), // Added
                fetch(API.teamHistory).then(res => res.json()),
                fetch(API.teamHitting).then(res => res.json()),
                fetch(API.teamPitching).then(res => res.json()),
                fetch(API.gamelogErrors).then(res => res.json()),
                fetch(API.typeDefinitions).then(res => res.json()),
                fetch(API.playerInfo).then(res => res.json()),
                fetch(API.currentSeasonInfo).then(res => res.json())
            ]);

            state.hittingStats = parseCompactData(hitting);
            state.pitchingStats = parseCompactData(pitching);
            state.teamHittingStats = parseCompactData(teamHitting);
            state.teamPitchingStats = parseCompactData(teamPitching);
            state.players = players;
            state.seasons = seasons;
            state.scoutingReports = scouting;
            state.glossaryData = glossary;
            state.divisions = divisions; // Added
            state.teamHistory = teamHistory;
            state.gamelogErrors = gamelogErrors;
            state.typeDefinitions = typeDefinitions;
            state.playerInfo = playerInfo;
            state.currentSeasonInfo = currentSeasonInfo;

            const seasonsWithStats = new Set();
            state.hittingStats.forEach(s => {
                if (s.Season && s.Season.startsWith('S') && !s.is_sub_row) {
                    seasonsWithStats.add(s.Season);
                }
            });
            state.pitchingStats.forEach(s => {
                if (s.Season && s.Season.startsWith('S') && !s.is_sub_row) {
                    seasonsWithStats.add(s.Season);
                }
            });
            state.seasonsWithStats = Array.from(seasonsWithStats).sort((a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1)));

            for (const id in players) {
                const player = players[id];
                state.playerMap.set(player.currentName.toLowerCase(), parseInt(id));
                if (player.formerNames) {
                    player.formerNames.forEach(name => {
                        state.playerMap.set(name.toLowerCase(), parseInt(id));
                    });
                }
            }

            elements.loader.style.display = 'none';
            elements.app.style.display = 'block';
            initializeApp();
        } catch (error) {
            console.error("Failed to load data:", error);
            elements.loader.innerHTML = "<p>Failed to load data. Please refresh the page.</p>";
        }
    };

    const seededRandom = (seed) => {
        return function() {
          var t = seed += 0x6D2B79F5;
          t = Math.imul(t ^ t >>> 15, t | 1);
          t ^= t + Math.imul(t ^ t >>> 7, t | 61);
          return ((t ^ t >>> 14) >>> 0) / 4294967296;
        }
    };

    const getFeaturedEntities = () => {
        const today = new Date();
        const seed = today.getFullYear() * 10000 + (today.getMonth() + 1) * 100 + today.getDate();
        const random = seededRandom(seed);

        const playerIds = Object.keys(state.players);
        
        // Select two distinct random players
        let randomIndex1 = Math.floor(random() * playerIds.length);
        let randomIndex2 = Math.floor(random() * playerIds.length);
        while (randomIndex1 === randomIndex2) { // Ensure distinct players
            randomIndex2 = Math.floor(random() * playerIds.length);
        }
        let featuredPlayerId1 = playerIds[randomIndex1];
        let featuredPlayerId2 = playerIds[randomIndex2];

        // --- Process Player 1 ---
        const playerHittingStats1 = state.hittingStats.filter(s => s['Hitter ID'] === parseInt(featuredPlayerId1));
        const playerPitchingStats1 = state.pitchingStats.filter(s => s['Pitcher ID'] === parseInt(featuredPlayerId1));
        const allPlayerStats1 = [...playerHittingStats1, ...playerPitchingStats1];

        let firstSeason1 = Infinity;
        let lastSeason1 = -Infinity;
        let mostRecentTeamAbbr1 = '';
        let mostRecentSeasonForPlayer1 = '';

        if (allPlayerStats1.length > 0) {
            for (const stat of allPlayerStats1) {
                if (stat.Season && stat.Season.startsWith('S')) {
                    const seasonNum = parseInt(stat.Season.slice(1));
                    if (!isNaN(seasonNum)) {
                        firstSeason1 = Math.min(firstSeason1, seasonNum);
                        lastSeason1 = Math.max(lastSeason1, seasonNum);
                    }
                }
            }
            const lastSeasonStats1 = allPlayerStats1
                .filter(s => s.Season && s.Season.startsWith('S') && !s.is_sub_row)
                .sort((a, b) => parseInt(b.Season.slice(1)) - parseInt(a.Season.slice(1)))[0];
            
            if (lastSeasonStats1) {
                mostRecentTeamAbbr1 = lastSeasonStats1['Last Team'] || lastSeasonStats1['Team'];
                mostRecentSeasonForPlayer1 = lastSeasonStats1.Season;
            }
        }
        const featuredPlayerSeasonRange1 = (firstSeason1 === Infinity || lastSeason1 === -Infinity) ? 'N/A' : (firstSeason1 === lastSeason1 ? `S${firstSeason1}` : `S${firstSeason1}-S${lastSeason1}`);
        const featuredPlayerMostRecentTeamKey1 = mostRecentTeamAbbr1 ? getFranchiseKeyFromAbbr(mostRecentTeamAbbr1, mostRecentSeasonForPlayer1) : '';
        const featuredPlayerMostRecentSeason1 = mostRecentSeasonForPlayer1;

        // --- Process Player 2 ---
        const playerHittingStats2 = state.hittingStats.filter(s => s['Hitter ID'] === parseInt(featuredPlayerId2));
        const playerPitchingStats2 = state.pitchingStats.filter(s => s['Pitcher ID'] === parseInt(featuredPlayerId2));
        const allPlayerStats2 = [...playerHittingStats2, ...playerPitchingStats2];

        let firstSeason2 = Infinity;
        let lastSeason2 = -Infinity;
        let mostRecentTeamAbbr2 = '';
        let mostRecentSeasonForPlayer2 = '';

        if (allPlayerStats2.length > 0) {
            for (const stat of allPlayerStats2) {
                if (stat.Season && stat.Season.startsWith('S')) {
                    const seasonNum = parseInt(stat.Season.slice(1));
                    if (!isNaN(seasonNum)) {
                        firstSeason2 = Math.min(firstSeason2, seasonNum);
                        lastSeason2 = Math.max(lastSeason2, seasonNum);
                    }
                }
            }
            const lastSeasonStats2 = allPlayerStats2
                .filter(s => s.Season && s.Season.startsWith('S') && !s.is_sub_row)
                .sort((a, b) => parseInt(b.Season.slice(1)) - parseInt(a.Season.slice(1)))[0];
            
            if (lastSeasonStats2) {
                mostRecentTeamAbbr2 = lastSeasonStats2['Last Team'] || lastSeasonStats2['Team'];
                mostRecentSeasonForPlayer2 = lastSeasonStats2.Season;
            }
        }
        const featuredPlayerSeasonRange2 = (firstSeason2 === Infinity || lastSeason2 === -Infinity) ? 'N/A' : (firstSeason2 === lastSeason2 ? `S${firstSeason2}` : `S${firstSeason2}-S${lastSeason2}`);
        const featuredPlayerMostRecentTeamKey2 = mostRecentTeamAbbr2 ? getFranchiseKeyFromAbbr(mostRecentTeamAbbr2, mostRecentSeasonForPlayer2) : '';
        const featuredPlayerMostRecentSeason2 = mostRecentSeasonForPlayer2;


        // --- Select a random team franchise and a valid season for it ---
        const teamKeys = Object.keys(state.teamHistory);
        const featuredTeamKey = teamKeys[Math.floor(random() * teamKeys.length)];
        const franchiseEntries = state.teamHistory[featuredTeamKey];
        let featuredTeamSeason = 'S1';

        if (franchiseEntries && franchiseEntries.length > 0) {
            const possibleSeasons = [];
            for (const entry of franchiseEntries) {
                for (let s = entry.start; s <= (entry.end === 9999 ? parseInt([...state.seasonsWithStats].sort((a,b)=>parseInt(b.slice(1))-parseInt(a.slice(1)))[0].slice(1)) : entry.end); s++) {
                    possibleSeasons.push(`S${s}`);
                }
            }
            if (possibleSeasons.length > 0) {
                featuredTeamSeason = possibleSeasons[Math.floor(random() * possibleSeasons.length)];
            }
        }

        return {
            featuredPlayerId1: parseInt(featuredPlayerId1),
            featuredPlayerSeasonRange1: featuredPlayerSeasonRange1,
            featuredPlayerMostRecentTeamKey1: featuredPlayerMostRecentTeamKey1,
            featuredPlayerMostRecentSeason1: featuredPlayerMostRecentSeason1,

            featuredPlayerId2: parseInt(featuredPlayerId2),
            featuredPlayerSeasonRange2: featuredPlayerSeasonRange2,
            featuredPlayerMostRecentTeamKey2: featuredPlayerMostRecentTeamKey2,
            featuredPlayerMostRecentSeason2: featuredPlayerMostRecentSeason2,

            featuredTeamKey: featuredTeamKey,
            featuredTeamSeason: featuredTeamSeason
        };
    };

    const updateView = () => {
        window.scrollTo(0, 0);
        const path = window.location.hash || '#/home';

        // Reset all views and tabs
        elements.homeView.style.display = 'none';
        elements.statsView.style.display = 'none';
        elements.leaderboardsView.style.display = 'none';
        elements.glossaryView.style.display = 'none';
        elements.teamStatsView.style.display = 'none';

        elements.homeTab.classList.remove('active');
        elements.statsTab.classList.remove('active');
        elements.teamStatsTab.classList.remove('active');
        elements.leaderboardsTab.classList.remove('active');
        elements.glossaryTab.classList.remove('active');

        // Parse URL parameters once if it's a team stats path
        let isTeamStatsPath = path.startsWith('#/team-stats');
        let seasonParam = null;
        let teamParam = null;

        if (isTeamStatsPath) {
            const url = new URL('http://dummy.com/' + path.substring(1));
            seasonParam = url.searchParams.get('season');
            teamParam = url.searchParams.get('team');
        }

        if (path === '#/home') {
            elements.homeView.style.display = 'block';
            elements.homeTab.classList.add('active');
            renderHome();
        } else if (path === '#/gamelog-errors') {
            elements.homeView.style.display = 'block';
            renderGamelogErrors();
        } else if (isTeamStatsPath && teamParam) { // Specific team page (has 'team' parameter)
            // This branch handles #/team-stats?season=S11&team=ATL
            displayTeamStatsPage(decodeURIComponent(teamParam), seasonParam);
            elements.teamStatsView.style.display = 'block';
            elements.teamStatsTab.classList.add('active');
        } else if (isTeamStatsPath) { // Team list page (might have 'season' but no 'team')
            // This branch handles #/team-stats or #/team-stats?season=S10
            displayTeamList(seasonParam);
            elements.teamStatsView.style.display = 'block';
            elements.teamStatsTab.classList.add('active');
        } else if (path === '#/stats' || path === '#/scouting') {
            const isStats = path === '#/stats';
            const isScouting = path === '#/scouting';
            elements.statsView.style.display = 'block';
            elements.statsTab.classList.toggle('active', isStats);
            if (state.currentPlayerId) {
                displayPlayerPage(state.currentPlayerId);
            } else {
                elements.statsContentDisplay.innerHTML = '<p>Search for a player to see their stats.</p>';
            }
        } else if (path === '#/leaderboards') {
            elements.leaderboardsView.style.display = 'block';
            elements.leaderboardsTab.classList.add('active');
            if (elements.leaderboardStatSelect.options.length <= 1) {
                populateLeaderboardStatSelect();
            }
        } else if (path === '#/glossary') {
            elements.glossaryView.style.display = 'flex';
            elements.glossaryTab.classList.add('active');
            renderGlossary();
        } else {
            // Default to home page if hash is invalid or empty
            window.location.hash = '#/home';
        }
    };

    const renderHome = () => {
        const { 
            featuredPlayerId1, featuredPlayerSeasonRange1, featuredPlayerMostRecentTeamKey1, featuredPlayerMostRecentSeason1,
            featuredPlayerId2, featuredPlayerSeasonRange2, featuredPlayerMostRecentTeamKey2, featuredPlayerMostRecentSeason2,
            featuredTeamKey, featuredTeamSeason 
        } = getFeaturedEntities();

        const featuredPlayer1 = state.players[featuredPlayerId1];
        const featuredPlayer2 = state.players[featuredPlayerId2];

        const featuredTeamName = getTeamNameBySeason(featuredTeamKey, featuredTeamSeason);
        const featuredTeamLogo = getTeamLogoBySeason(featuredTeamKey, featuredTeamSeason);

        const playerMostRecentTeamLogo1 = getTeamLogoBySeason(featuredPlayerMostRecentTeamKey1, featuredPlayerMostRecentSeason1);
        const playerMostRecentTeamLogo2 = getTeamLogoBySeason(featuredPlayerMostRecentTeamKey2, featuredPlayerMostRecentSeason2);

        elements.homeView.innerHTML = `
            <div class="welcome-container">
                <h2 class="section-title">Welcome to MLR Reference!</h2>
                <p>MLR Reference is your (unofficial) guide to all regular season stats for Major League Redditball (MLR).</p>
                <p>Here you can find:</p>
                <ul>
                    <li><a href="#/stats"><strong>Player Stats:</strong></a> Detailed batting and pitching statistics for every player in MLR history. Players can be searched by name (including former names) or player ID.</li>
                    <li><a href="#/team-stats"><strong>Team Stats:</strong></a> Season-by-season standings and team statistics.</li>
                    <li><a href="#/leaderboards"><strong>Leaderboards:</strong></a> All-time and single-season leaderboards for a variety of stats.</li>
                    <li><a href="#/glossary"><strong>Glossary:</strong></a> Definitions and equations for advanced and calculated stats.</li>
                    <li><a href="#/gamelog-errors"><strong>Known Gamelog Errors:</strong></a> A list of known errors in the gamelogs. All these errors have been corrected for this app.</li>
                    <li><a href="https://forms.gle/nmLNL5PbF6bXrXpo9" target="_blank"><strong>Feedback:</strong></a> Have a suggestion or found a bug? Let me know!</li>
                </ul>
                <br>
                <p>Potential future features:</p>
                <ul>
                    <li> Box scores for each game.</li>
                    <li> Postseason stats.</li>
                    <li> Awards (including All-Star appearances, MVP, etc.).</li>
                    <li> Player comparison.</li>
                    <li> Outcome calculator.</li>
                </ul>

                <h3 class="section-title">Today's Features</h3>
                <div class="featured-section">
                    <div class="featured-item">
                        <h4>Featured Player</h4>
                        <a href="#/stats" class="player-link" data-player-id="${featuredPlayerId1}">
                            ${playerMostRecentTeamLogo1 ? `<img src="${playerMostRecentTeamLogo1}" alt="${featuredPlayer1.currentName} team logo" class="team-list-logo">` : ''}
                            <p>${featuredPlayer1 ? featuredPlayer1.currentName : 'N/A'}</p>
                            <p class="featured-player-season-range">${featuredPlayerSeasonRange1}</p>
                        </a>
                    </div>
                    <div class="featured-item">
                        <h4>Featured Player</h4>
                        <a href="#/stats" class="player-link" data-player-id="${featuredPlayerId2}">
                            ${playerMostRecentTeamLogo2 ? `<img src="${playerMostRecentTeamLogo2}" alt="${featuredPlayer2.currentName} team logo" class="team-list-logo">` : ''}
                            <p>${featuredPlayer2 ? featuredPlayer2.currentName : 'N/A'}</p>
                            <p class="featured-player-season-range">${featuredPlayerSeasonRange2}</p>
                        </a>
                    </div>
                    <div class="featured-item">
                        <h4>Featured Team</h4>
                        <a href="#/team-stats?season=${featuredTeamSeason}&team=${featuredTeamKey}">
                            ${featuredTeamLogo ? `<img src="${featuredTeamLogo}" alt="${featuredTeamName} logo" class="team-list-logo">` : ''}
                            <p>${featuredTeamSeason} ${featuredTeamName || 'N/A'}</p>
                        </a>
                    </div>
                    <div class="featured-item action-item">
                        <h4>Discover More!</h4>
                        <button id="random-player-button" class="action-button">Random Player</button>
                    </div>
                </div>
                <br>

                <h3 class="section-title">Frequently Asked Questions</h3>
                <p>Why is my W-L record different than it appears in the roster sheet?</p>
                <p><i>The roster sheet requires starting pitchers to complete at least 3 innings (1/2 game) to qualify for the Win. MLR Reference requires starting pitchers to complete at least 3 1/3 innings (5/9 game, the same ratio as MLB) to qualify for the Win.</i></p>
                <br>
                <p>Why is my WAR different than it appears in the roster sheet?</p>
                <p><i>Like any good baseball statistics site, MLR Reference has its own WAR formula. MLR Reference WAR (also known as "cheWAR") is calculated using RE24. More information about WAR calculation can be found in the glossary.</i></p>
                <br>
                <p>Why do my franchise total stat lines include teams I've never played for?</p>
                <p><i>The franchise total stat lines use the abbreviations that are currently used by the franchise. For example, S2-S5 Texas Rangers has been Cleveland Guardians since S6, so even players who only played during the TEX era will have CLE in their franchise totals.</i></p>
                <br>
                <p>Why does S2 San Diego Padres have a different W-L record than the roster sheet?</p>
                <p><i>The roster sheet is wrong.</i></p>
            </div>
        `;
    };

    const renderGlossary = () => {
        const sidebar = document.getElementById('glossary-sidebar');
        const content = document.getElementById('glossary-content');
        
        sidebar.innerHTML = '';
        content.innerHTML = '<p>Select a stat from the sidebar to view its definition.</p>';

        for (const groupName in GLOSSARY_GROUPS) {
            const groupHeader = document.createElement('h4');
            groupHeader.className = 'glossary-group-header';
            groupHeader.innerHTML = `<span class="arrow">&#9658;</span> ${groupName}`;
            sidebar.appendChild(groupHeader);
    
            const statList = document.createElement('ul');
            statList.className = 'glossary-stat-list collapsed';

            groupHeader.addEventListener('click', () => {
                groupHeader.classList.toggle('expanded');
                statList.classList.toggle('collapsed');
            });
    
            const statsInGroup = GLOSSARY_GROUPS[groupName];
            statsInGroup.forEach(stat => {
                if (state.glossaryData[stat]) {
                    const statItem = document.createElement('li');
                    statItem.textContent = `${stat} - ${state.glossaryData[stat].name}`;
                    statItem.dataset.stat = stat;
                    statItem.addEventListener('click', (e) => {
                        e.stopPropagation(); // Prevent group from collapsing when item is clicked
                        displayGlossaryEntry(stat);
                        document.querySelectorAll('#glossary-sidebar li').forEach(item => item.classList.remove('active'));
                        statItem.classList.add('active');
                    });
                    statList.appendChild(statItem);
                }
            });
            sidebar.appendChild(statList);
        }
    };

    const displayGlossaryEntry = (stat) => {
        const content = document.getElementById('glossary-content');
        const entry = state.glossaryData[stat];
        if (!entry) {
            content.innerHTML = '<p>Select a stat from the sidebar.</p>';
            return;
        }

        let entryHTML = `<h2 class="section-title">${stat} - ${entry.name}</h2>`;
        entryHTML += `<p>${entry.definition}</p>`;

        if (entry.conditional_rules) {
            entryHTML += '<h4>Conditional Rules:</h4>';
            entryHTML += '<ul>';
            entry.conditional_rules.forEach(rule => {
                entryHTML += `<li>${rule}</li>`;
            });
            entryHTML += '</ul>';
        }

        if (entry.sections) {
            entryHTML += entry.sections.map(section => `<h4>${section.title}</h4>${section.content}`).join('');
        }
        
        content.innerHTML = entryHTML;
    };

    const renderGamelogErrors = () => {
        let content = '<div class="welcome-container">';
        content += '<h2 class="section-title">Known Gamelog Errors</h2>';

        if (state.gamelogErrors && state.gamelogErrors.length > 0) {
            state.gamelogErrors.forEach(error => {
                const header = `${error.season}.${error.session} (Game ${error.game}), ${error.away_team} @ ${error.home_team}`;
                content += `<div class="gamelog-error-item">`;
                content += `<h4>${header.replace(/null/g, 'N/A')}</h4>`;
                content += `<p>${error.description || 'No description provided.'}</p>`;
                content += `</div>`;
            });
        } else {
            content += '<p>No known gamelog errors.</p>';
        }

        content += '</div>';
        elements.homeView.innerHTML = content;
    };

    const initializeApp = () => {
        window.addEventListener('hashchange', updateView);

        const themeSwitch = elements.themeSwitch;
        const currentTheme = localStorage.getItem('theme');

        function setTheme(theme) {
            if (theme === 'light-mode') {
                document.documentElement.classList.add('light-mode');
                themeSwitch.checked = true;
            } else {
                document.documentElement.classList.remove('light-mode');
                themeSwitch.checked = false;
            }
        }

        if (currentTheme) {
            setTheme(currentTheme);
        } else {
			setTheme('dark-mode');
		}

        themeSwitch.addEventListener('change', () => {
            if (themeSwitch.checked) {
                document.documentElement.classList.add('light-mode');
                localStorage.setItem('theme', 'light-mode');
            } else {
                document.documentElement.classList.remove('light-mode');
                localStorage.setItem('theme', 'dark-mode');
            }
            updateView();
        });

        
        const leaderboardLengthInput = elements.leaderboardLength;
        
        // Set default minimums for leaderboards
        elements.minPa.value = (2.0).toFixed(1);
        elements.minOuts.value = 3;
        elements.minAttempts.value = 3;
        elements.minDecisions.value = 3;

        updateView(); // Initial view
        
        elements.playerSearch.addEventListener('input', handlePlayerSearch);
        elements.leaderboardButton.addEventListener('click', handleLeaderboardView);
        elements.leaderboardTypeSelect.addEventListener('change', populateLeaderboardStatSelect);
        elements.leaderboardStatSelect.addEventListener('change', handleStatSelectChange);
        populateTeamFilter();

        elements.homeTab.addEventListener('click', () => { window.location.hash = '#/home'; });
        elements.statsTab.addEventListener('click', () => { window.location.hash = '#/stats'; });
        elements.teamStatsTab.addEventListener('click', () => { window.location.hash = '#/team-stats'; });
        elements.leaderboardsTab.addEventListener('click', () => { window.location.hash = '#/leaderboards'; });
        elements.glossaryTab.addEventListener('click', () => { window.location.hash = '#/glossary'; });

        elements.app.addEventListener('click', (event) => {
            const teamLink = event.target.closest('.team-link');
            if (teamLink) {
                const team = teamLink.dataset.team;
                const season = teamLink.dataset.season;
                if (team && season) {
                    const hashPath = `#/team-stats?season=${season}&team=${team}`;
                    state.lastTeamStatsUrl = hashPath; // Update state for immediate use
                    window.location.hash = hashPath; // Still update hash for immediate view change
                }
            }

            const playerLink = event.target.closest('.player-link');
            if (playerLink) {
                const playerId = parseInt(playerLink.dataset.playerId, 10);
                if (!isNaN(playerId)) {
                    const playerName = state.players[playerId].currentName;
                    window.location.hash = '#/stats'; // Go to player stats view
                    elements.playerSearch.value = playerName;
                    elements.playerSuggestions.innerHTML = '';
                    displayPlayerPage(playerId);
                }
            }

            // Existing leaderboard player click logic
            const leaderboardPlayerCell = event.target.closest('.player-name-cell');
            if (leaderboardPlayerCell && leaderboardPlayerCell.dataset.playerId) {
                const playerId = parseInt(leaderboardPlayerCell.dataset.playerId, 10);
                if (!isNaN(playerId)) {
                    const playerName = state.players[playerId].currentName;
                    window.location.hash = '#/stats';
                    elements.playerSearch.value = playerName;
                    elements.playerSuggestions.innerHTML = '';
                    displayPlayerPage(playerId);
                }
            }

            // Handle random player button click via delegation
            const randomPlayerButton = event.target.closest('#random-player-button');
            if (randomPlayerButton) {
                goToRandomPlayerPage();
            }
        });
    };

    const populateLeaderboardStatSelect = () => {
        const type = elements.leaderboardTypeSelect.value;
        const statSelect = elements.leaderboardStatSelect;
        const previouslySelectedStat = statSelect.value;
        const typeFilter = elements.leaderboardTypeFilter;
        const previouslySelectedType = typeFilter.value;

        if (type === 'batting') {
            elements.battingMinimumControls.style.display = 'inline-block';
            elements.pitchingMinimumControls.style.display = 'none';
        } else {
            elements.battingMinimumControls.style.display = 'none';
            elements.pitchingMinimumControls.style.display = 'inline-block';
        }

        statSelect.innerHTML = '<option value="">-- Select Stat --</option>'; // Clear existing options

        const stats = (type === 'batting') 
            ? Object.values(STAT_DEFINITIONS.batting_tables).flat().concat(LEADERBOARD_ONLY_STATS.hitting)
            : Object.values(STAT_DEFINITIONS.pitching_tables).flat().concat(LEADERBOARD_ONLY_STATS.pitching);

        const uniqueStats = [...new Set(stats)].sort();
        let newOptionsExist = false;
        uniqueStats.forEach(stat => {
            if (stat === 'Season' || stat === 'Team' || stat === 'Type') return;
            const option = document.createElement('option');
            option.value = stat;
            option.textContent = stat;
            statSelect.appendChild(option);
            if (stat === previouslySelectedStat) {
                newOptionsExist = true;
            }
        });

        if (newOptionsExist) {
            statSelect.value = previouslySelectedStat;
        }

        // --- New logic to populate type filter ---
        typeFilter.innerHTML = '<option value="">All Types</option>';
        const playerTypesMap = (type === 'batting') ? state.typeDefinitions.batting : state.typeDefinitions.pitching;
        
        if (playerTypesMap) {
            const mainTypes = new Set();
            if (type === 'batting') {
                for (const typeKey in playerTypesMap) {
                    mainTypes.add(typeKey);
                }
            } else { // pitching
                for (const typeKey in playerTypesMap) {
                    const mainType = typeKey.split('-')[0];
                    mainTypes.add(mainType);
                }
            }
            const sortedMainTypes = Array.from(mainTypes).sort();

            sortedMainTypes.forEach(mainType => {
                const option = document.createElement('option');
                option.value = mainType;
                option.textContent = mainType;
                typeFilter.appendChild(option);
            });
        }
        if (previouslySelectedType && typeFilter.querySelector(`option[value="${previouslySelectedType}"]`)) {
            typeFilter.value = previouslySelectedType;
        }
    };

    const handleLeaderboardView = () => {
        console.log('handleLeaderboardView called');
        const stat = elements.leaderboardStatSelect.value;
        if (!stat) return;
        console.log('Selected stat:', stat);

        const type = elements.leaderboardTypeSelect.value;
        const selectedTeam = elements.leaderboardTeamFilter.value;
        const isHitting = type === 'batting';
        const reverseSort = elements.reverseSort.checked;
        const sortModifier = reverseSort ? -1 : 1;

        const qualMultiplier = isHitting ? 2.0 : 1.0;
        
        let statKey = stat;
        let data = isHitting ? state.hittingStats : state.pitchingStats;
        const selectedType = elements.leaderboardTypeFilter.value;
        if (selectedType) {
            if (isHitting) {
                data = data.filter(p => p.Type === selectedType);
            } else { // isPitching
                data = data.filter(p => p.Type && p.Type.startsWith(selectedType));
            }
        }
        
        if (isHitting) {
            if (stat === 'SO') statKey = 'K';
            else if (stat === 'BA') statKey = 'AVG';
        } else { // isPitching
            if (stat === 'SO') statKey = 'K';
            else if (stat === 'ER') statKey = 'R';
            else if (stat === 'H6') statKey = 'H/6';
            else if (stat === 'HR6') statKey = 'HR/6';
            else if (stat === 'BB6') statKey = 'BB/6';
            else if (stat === 'SO6') statKey = 'K/6';
            else if (stat === 'SO/BB') statKey = 'K/BB';
            else if (stat === 'GB%') statKey = 'GB%_A';
            else if (stat === 'FB%') statKey = 'FB%_A';
            else if (stat === 'GB/FB') statKey = 'GB/FB_A';
            else if (stat === 'BA') statKey = 'BAA';
            else if (stat === 'OBP') statKey = 'OBPA';
            else if (stat === 'SLG') statKey = 'SLGA';
            else if (stat === 'OPS') statKey = 'OPSA';
            else if (stat === 'BABIP') statKey = 'BABIP_A';
            else if (stat === 'HR%') statKey = 'HR%_A';
            else if (stat === 'K%') statKey = 'K%_A';
            else if (stat === 'BB%') statKey = 'BB%_A';
            else if (stat === 'SB') statKey = 'SB_A';
            else if (stat === 'CS') statKey = 'CS_A';
            else if (stat === 'SB%') statKey = 'SB%_A';
            else if (stat === '2B') statKey = '2B_A';
            else if (stat === '3B') statKey = '3B_A';
        }
        
        const leaderboards = {};
        let lowerIsBetterStats = [];
        if (isHitting) {
            lowerIsBetterStats = ['Avg Diff'];
        } else { // isPitching
            lowerIsBetterStats = [
                'ERA', 'WHIP', 'FIP', 'RE24',
                'BAA', 'OBPA', 'SLGA', 'OPSA', 'BABIP_A',
                'H6', 'HR6', 'BB6',
                'BA', 'OBP', 'SLG', 'OPS', 'BABIP',
                'HR%', 'BB%', 'SB%', 'ERA-'
            ];
        }
        const lowerIsBetter = lowerIsBetterStats.includes(stat);
        
        if (stat === 'W-L%') {
            const sortFn = (a, b) => {
                const diff = (b['W-L%'] || 0) - (a['W-L%'] || 0);
                if (diff !== 0) return sortModifier * diff;
                const a_decisions = (a.W || 0) + (a.L || 0);
                const b_decisions = (b.W || 0) + (b.L || 0);
                return sortModifier * (b_decisions - a_decisions);
            };

            // All-Time
            let allTimeLeaderboardData;
            if (selectedType) {
                allTimeLeaderboardData = data.filter(p => p.Season === 'Type' && p.Type === selectedType);
            } else if (selectedTeam) {
                allTimeLeaderboardData = data.filter(p => p.Season === 'Franchise' && p.Team === selectedTeam);
            } else {
                allTimeLeaderboardData = data.filter(p => p.Season === 'Career');
            }
            const min_decisions_career = 10;
            let allTimeLeaderboard = allTimeLeaderboardData.filter(p => ((p.W || 0) + (p.L || 0)) >= min_decisions_career);
            allTimeLeaderboard.sort(sortFn);
            leaderboards['All-Time'] = {
                type: 'all-time',
                data: allTimeLeaderboard,
                isCountingStat: false,
                min_qual: min_decisions_career,
                min_qual_key: 'Decisions'
            };

            // Single Season
            let singleSeasonData = data.filter(p => p.Season !== 'Career' && p.Season !== 'Franchise' && p.Season !== 'Type');
            if (selectedTeam) {
                const franchise = state.teamHistory[selectedTeam];
                if (franchise) {
                    singleSeasonData = singleSeasonData.filter(p => {
                        const seasonNum = parseInt(p.Season.slice(1));
                        if (isNaN(seasonNum)) return false;
                        return franchise.some(f => p.Team === f.abbr && seasonNum >= f.start && seasonNum <= f.end);
                    });
                } else {
                    singleSeasonData = singleSeasonData.filter(p => p.Team === selectedTeam);
                }
            } else {
                singleSeasonData = singleSeasonData.filter(p => !p.is_sub_row);
            }
            const min_decisions_season = parseInt(elements.minDecisions.value) || 3;
            let singleSeasonLeaderboard = singleSeasonData.filter(p => ((p.W || 0) + (p.L || 0)) >= min_decisions_season);
            singleSeasonLeaderboard.sort(sortFn);
            leaderboards['Single Season'] = {
                type: 'single-season',
                data: singleSeasonLeaderboard,
                isCountingStat: false,
                min_qual: min_decisions_season,
                min_qual_key: 'Decisions'
            };

            // Individual Seasons
            const allSeasons = [...state.seasonsWithStats].sort((a, b) => parseInt(b.slice(1)) - parseInt(a.slice(1)));
            for (const season of allSeasons) {
                let seasonData = data.filter(p => p.Season === season);
                if (selectedTeam) {
                    const franchise = state.teamHistory[selectedTeam];
                    if (franchise) {
                        const seasonNum = parseInt(season.slice(1));
                        const correctAbbr = franchise.find(f => seasonNum >= f.start && seasonNum <= f.end)?.abbr;
                        if (correctAbbr) {
                            seasonData = seasonData.filter(p => p.Team === correctAbbr);
                        } else { // This franchise didn't exist this season.
                            seasonData = []; 
                        }
                    } else {
                        seasonData = seasonData.filter(p => p.Team === selectedTeam);
                    }
                } else {
                    seasonData = seasonData.filter(p => !p.is_sub_row);
                }
                let leaderboardData = seasonData.filter(p => ((p.W || 0) + (p.L || 0)) >= min_decisions_season);
                leaderboardData.sort(sortFn);
                leaderboards[season] = {
                    type: 'season',
                    data: leaderboardData,
                    isCountingStat: false,
                    min_qual: min_decisions_season,
                    min_qual_key: 'Decisions'
                };
            }
        } else if (stat === 'SB%') {
            const sbKey = isHitting ? 'SB' : 'SB_A';
            const csKey = isHitting ? 'CS' : 'CS_A';

            const sortFn = (a, b) => {
                const diff = lowerIsBetter
                    ? (a[statKey] || 0) - (b[statKey] || 0)
                    : (b[statKey] || 0) - (a[statKey] || 0);
                if (diff !== 0) return sortModifier * diff;
                const a_attempts = (parseFloat(a[sbKey]) || 0) + (parseFloat(a[csKey]) || 0);
                const b_attempts = (parseFloat(b[sbKey]) || 0) + (parseFloat(b[csKey]) || 0);
                return sortModifier * (b_attempts - a_attempts);
            };

            // All-Time
            let allTimeLeaderboardData;
            if (selectedType) {
                allTimeLeaderboardData = data.filter(p => p.Season === 'Type' && p.Type === selectedType);
            } else if (selectedTeam) {
                allTimeLeaderboardData = data.filter(p => p.Season === 'Franchise' && p.Team === selectedTeam);
            } else {
                allTimeLeaderboardData = data.filter(p => p.Season === 'Career');
            }
            const min_attempts_career = 10;
            let allTimeLeaderboard = allTimeLeaderboardData.filter(p => ((p[sbKey] || 0) + (p[csKey] || 0)) >= min_attempts_career);
            allTimeLeaderboard.sort(sortFn);
            leaderboards['All-Time'] = {
                type: 'all-time',
                data: allTimeLeaderboard,
                isCountingStat: false,
                min_qual: min_attempts_career,
                min_qual_key: 'Attempts'
            };

            // Single Season
            let singleSeasonData = data.filter(p => p.Season !== 'Career' && p.Season !== 'Franchise' && p.Season !== 'Type');
            if (selectedTeam) {
                const franchise = state.teamHistory[selectedTeam];
                if (franchise) {
                    singleSeasonData = singleSeasonData.filter(p => {
                        const seasonNum = parseInt(p.Season.slice(1));
                        if (isNaN(seasonNum)) return false;
                        return franchise.some(f => p.Team === f.abbr && seasonNum >= f.start && seasonNum <= f.end);
                    });
                } else {
                    singleSeasonData = singleSeasonData.filter(p => p.Team === selectedTeam);
                }
            } else {
                singleSeasonData = singleSeasonData.filter(p => !p.is_sub_row);
            }
            const min_attempts_season = parseInt(elements.minAttempts.value) || 3;
            let singleSeasonLeaderboard = singleSeasonData.filter(p => ((p[sbKey] || 0) + (p[csKey] || 0)) >= min_attempts_season);
            singleSeasonLeaderboard.sort(sortFn);
            leaderboards['Single Season'] = {
                type: 'single-season',
                data: singleSeasonLeaderboard,
                isCountingStat: false,
                min_qual: min_attempts_season,
                min_qual_key: 'Attempts'
            };

            // Individual Seasons
            const allSeasons = [...state.seasonsWithStats].sort((a, b) => parseInt(b.slice(1)) - parseInt(a.slice(1)));
            for (const season of allSeasons) {
                let seasonData = data.filter(p => p.Season === season);
                if (selectedTeam) {
                    const franchise = state.teamHistory[selectedTeam];
                    if (franchise) {
                        const seasonNum = parseInt(season.slice(1));
                        const correctAbbr = franchise.find(f => seasonNum >= f.start && seasonNum <= f.end)?.abbr;
                        if (correctAbbr) {
                            seasonData = seasonData.filter(p => p.Team === correctAbbr);
                        } else { // This franchise didn't exist this season.
                            seasonData = []; 
                        }
                    } else {
                        seasonData = seasonData.filter(p => p.Team === selectedTeam);
                    }
                } else {
                    seasonData = seasonData.filter(p => !p.is_sub_row);
                }
                let leaderboardData = seasonData.filter(p => ((p[sbKey] || 0) + (p[csKey] || 0)) >= min_attempts_season);
                leaderboardData.sort(sortFn);
                leaderboards[season] = {
                    type: 'season',
                    data: leaderboardData,
                    isCountingStat: false,
                    min_qual: min_attempts_season,
                    min_qual_key: 'Attempts'
                };
            }
        } else {
            const isCountingStat = COUNTING_STATS.includes(stat);
            
            let min_qual_key;
            if (isHitting) {
                min_qual_key = 'PA';
                if (stat === 'GO') {
                    data.forEach(p => { p.GO = (p.LGO || 0) + (p.RGO || 0); });
                }
            } else { // isPitching
                min_qual_key = 'IP';
                if (stat === 'GO') {
                    data.forEach(p => { p.GO = (p.LGO || 0) + (p.RGO || 0); });
                }
            }
            
            const statsThatCanBeNegative = ['WAR', 'WPA', 'RE24'];

            // All-Time
            let allTimeLeaderboardData;
            if (selectedType) {
                allTimeLeaderboardData = data.filter(p => p.Season === 'Type' && p.Type === selectedType);
            } else if (selectedTeam) {
                allTimeLeaderboardData = data.filter(p => p.Season === 'Franchise' && p.Team === selectedTeam);
            } else {
                allTimeLeaderboardData = data.filter(p => p.Season === 'Career');
            }
            
            const min_qual_career = isHitting ? 100 : 50;
            let allTimeLeaderboard = isCountingStat ? allTimeLeaderboardData : allTimeLeaderboardData.filter(p => (p[min_qual_key] || 0) >= min_qual_career);
            if (isCountingStat && !statsThatCanBeNegative.includes(stat)) {
                allTimeLeaderboard = allTimeLeaderboard.filter(p => p[statKey] > 0);
            }
            allTimeLeaderboard.sort((a, b) => sortModifier * (lowerIsBetter ? (a[statKey] || 0) - (b[statKey] || 0) : (b[statKey] || 0) - (a[statKey] || 0)));
            leaderboards['All-Time'] = {
                type: 'all-time',
                data: allTimeLeaderboard,
                isCountingStat: isCountingStat,
                min_qual: min_qual_career,
                min_qual_key: min_qual_key
            };
            // Single Season
            let singleSeasonData = data.filter(p => p.Season !== 'Career' && p.Season !== 'Franchise' && p.Season !== 'Type');

            // Exclude current season from Single Season leaderboards if it's not halfway through
            const currentSeason = state.currentSeasonInfo.season;
            if (currentSeason) {
                const totalSessions = state.seasons[currentSeason] || 0;
                const sessionsSoFar = state.currentSeasonInfo.session || 0;
                if (totalSessions > 0 && sessionsSoFar <= totalSessions / 2) {
                    singleSeasonData = singleSeasonData.filter(p => p.Season !== currentSeason);
                }
            }

            if (selectedTeam) {
                const franchise = state.teamHistory[selectedTeam];
                if (franchise) {
                    singleSeasonData = singleSeasonData.filter(p => {
                        const seasonNum = parseInt(p.Season.slice(1));
                        if (isNaN(seasonNum)) return false;
                        return franchise.some(f => p.Team === f.abbr && seasonNum >= f.start && seasonNum <= f.end);
                    });
                } else {
                    singleSeasonData = singleSeasonData.filter(p => p.Team === selectedTeam);
                }
            } else {
                singleSeasonData = singleSeasonData.filter(p => !p.is_sub_row);
            }
            let singleSeasonLeaderboard;
            if (isCountingStat) {
                singleSeasonLeaderboard = singleSeasonData;
            } else {
                singleSeasonLeaderboard = singleSeasonData.filter(p => {
                    const season = p.Season;
                    const gamesInSeason = state.seasons[season] || 0;
                    if (gamesInSeason === 0) return false;
                    
                    let sessionsToUse = gamesInSeason;
                    // For the most recent season, use sessions so far.
                    if (season === state.currentSeasonInfo.season) {
                        sessionsToUse = state.currentSeasonInfo.session || gamesInSeason;
                    }
            
                    if (isHitting) {
                        const pa_per_session = parseFloat(elements.minPa.value) || 2.0;
                        const min_pa = pa_per_session * sessionsToUse;
                        return (p.PA || 0) >= min_pa;
                    } else { // isPitching
                        const outs_per_session = parseInt(elements.minOuts.value) || 3;
                        const min_outs = outs_per_session * sessionsToUse;
                        const player_ip = p.IP || 0;
                        const player_outs = Math.round(player_ip * 3);
                        return player_outs >= min_outs;
                    }
                });
            }
            if (isCountingStat && !statsThatCanBeNegative.includes(stat)) {
                singleSeasonLeaderboard = singleSeasonLeaderboard.filter(p => p[statKey] > 0);
            }
            singleSeasonLeaderboard.sort((a, b) => sortModifier * (lowerIsBetter ? (a[statKey] || 0) - (b[statKey] || 0) : (b[statKey] || 0) - (a[statKey] || 0)));
            leaderboards['Single Season'] = {
                type: 'single-season',
                data: singleSeasonLeaderboard,
                isCountingStat: isCountingStat,
                min_qual_key: min_qual_key
            };

            // Individual Seasons
            const allSeasons = [...state.seasonsWithStats].sort((a, b) => parseInt(b.slice(1)) - parseInt(a.slice(1)));
                                                for (const season of allSeasons) {
                                                    let seasonData = data.filter(p => p.Season === season);
                                                    if (selectedTeam) {
                                                        const franchise = state.teamHistory[selectedTeam];
                                                        if (franchise) {
                                                            const seasonNum = parseInt(season.slice(1));
                                                            const correctAbbr = franchise.find(f => seasonNum >= f.start && seasonNum <= f.end)?.abbr;
                                                            if (correctAbbr) {
                                                                seasonData = seasonData.filter(p => p.Team === correctAbbr);
                                                            } else { // This franchise didn't exist this season.
                                                                seasonData = []; 
                                                            }
                                                        } else {
                                                            seasonData = seasonData.filter(p => p.Team === selectedTeam);
                                                        }
                                                    } else {
                                                        seasonData = seasonData.filter(p => !p.is_sub_row);
                                                    }
                                    
                                                    const gamesInSeason = state.seasons[season] || 0;
                                                    let sessionsToUse = gamesInSeason;

                                                    // For the most recent season, use sessions so far.
                                                    if (season === state.currentSeasonInfo.season) {
                                                        sessionsToUse = state.currentSeasonInfo.session || gamesInSeason;
                                                    }

                                                    let min_qual;
                                                    const min_qual_display_key = isHitting ? 'PA' : 'Outs';

                                                    if (isHitting) {
                                                        const pa_per_session = parseFloat(elements.minPa.value) || 2.0;
                                                        min_qual = pa_per_session * sessionsToUse;
                                                    } else {
                                                        const outs_per_session = parseInt(elements.minOuts.value) || 3;
                                                        min_qual = outs_per_session * sessionsToUse;
                                                    }
                                    
                                                    let leaderboardData = isCountingStat ? seasonData : seasonData.filter(p => {
                                                        if (isHitting) {
                                                            return (p[min_qual_key] || 0) >= min_qual;
                                                        } else { // isPitching
                                                            const player_ip = p.IP || 0;
                                                            const player_outs = Math.round(player_ip * 3);
                                                            return player_outs >= min_qual;
                                                        }
                                                    });
                                    
                                                    if (isCountingStat && !statsThatCanBeNegative.includes(stat)) {
                                                        leaderboardData = leaderboardData.filter(p => p[statKey] > 0);
                                                    }
                                                    leaderboardData.sort((a, b) => sortModifier * (lowerIsBetter ? (a[statKey] || 0) - (b[statKey] || 0) : (b[statKey] || 0) - (a[statKey] || 0)));
                                                    leaderboards[season] = {
                                                        type: 'season',
                                                        data: leaderboardData,
                                                        isCountingStat: isCountingStat,
                                                        min_qual: min_qual,
                                                        min_qual_key: min_qual_display_key
                                                    };
                                                }
        }
        renderLeaderboardGrid(leaderboards, stat, statKey, isHitting);
    };

    const renderLeaderboardGrid = (leaderboards, stat, statKey, isHitting) => {
        console.log('renderLeaderboardGrid called with leaderboards:', JSON.stringify(leaderboards, null, 2));
        const leaderboardSize = parseInt(elements.leaderboardLength.value) || 10;
        elements.leaderboardsContentDisplay.innerHTML = `<h2 class="section-title">${stat} Leaderboards</h2>`;

        const gridContainer = document.createElement('div');
        gridContainer.className = 'leaderboard-grid';

        const gridOrder = ['All-Time', 'Single Season', ...[...state.seasonsWithStats].sort((a, b) => parseInt(b.slice(1)) - parseInt(a.slice(1)))];

        for (const key of gridOrder) {
            const leaderboardInfo = leaderboards[key];
            if (!leaderboardInfo) continue;
            
            const fullLeaderboard = leaderboardInfo.data;

            const arePlayersTied = (p1, p2) => {
                if (!p1 || !p2) return false;
                if (p1[statKey] !== p2[statKey]) return false;
                if (stat === 'W-L%') {
                    const p1_dec = (p1.W || 0) + (p1.L || 0);
                    const p2_dec = (p2.W || 0) + (p2.L || 0);
                    return p1_dec === p2_dec;
                }
                if (stat === 'SB%') {
                    const sbKey = isHitting ? 'SB' : 'SB_A';
                    const csKey = isHitting ? 'CS' : 'CS_A';
                    const p1_att = (p1[sbKey] || 0) + (p1[csKey] || 0);
                    const p2_att = (p2[sbKey] || 0) + (p2[csKey] || 0);
                    return p1_att === p2_att;
                }
                return true; // Tied on primary stat, no tie-breaker
            };

            let leaderboard = fullLeaderboard.slice(0, leaderboardSize);
            let tieInfo = null;

            if (fullLeaderboard.length > leaderboardSize) {
                const lastPlayerInSlice = fullLeaderboard[leaderboardSize - 1];
                const firstPlayerOutOfSlice = fullLeaderboard[leaderboardSize];

                if (arePlayersTied(lastPlayerInSlice, firstPlayerOutOfSlice)) {
                    const tieValue = lastPlayerInSlice[statKey];
                    if (tieValue !== null && tieValue !== undefined) {
                        let firstTieIndex = leaderboardSize - 1;
                        while (firstTieIndex > 0 && arePlayersTied(fullLeaderboard[firstTieIndex - 1], lastPlayerInSlice)) {
                            firstTieIndex--;
                        }

                        const tieCount = fullLeaderboard.filter(p => arePlayersTied(p, lastPlayerInSlice)).length;
                        
                        leaderboard = fullLeaderboard.slice(0, firstTieIndex);
                        tieInfo = { count: tieCount, value: tieValue };
                    }
                }
            }

            const seasonCard = document.createElement('div');
            seasonCard.className = 'leaderboard-card';

            let title;
            if (leaderboardInfo.type === 'all-time') {
                title = `<h4>All-Time</h4>`;
            } else if (leaderboardInfo.type === 'single-season') {
                title = `<h4>Single Season</h4>`;
            } else {
                title = `<h4>Season ${key.slice(1)}</h4>`;
            }

            if (!leaderboardInfo.isCountingStat && leaderboardInfo.type !== 'single-season') {
                let display_min_qual = leaderboardInfo.min_qual;
                let display_min_qual_key = leaderboardInfo.min_qual_key;

                if (leaderboardInfo.min_qual_key === 'Outs') {
                    display_min_qual = leaderboardInfo.min_qual / 3; // Convert outs to IP float
                    display_min_qual_key = 'IP';
                } else if (leaderboardInfo.min_qual_key === 'PA') {
                    display_min_qual = Math.ceil(leaderboardInfo.min_qual);
                }
                const qual_text = `${formatStat(display_min_qual_key, display_min_qual)} ${display_min_qual_key}`;
                title += `<p class="qualifier">(${qual_text} min)</p>`;
            }
            seasonCard.innerHTML = title;

            const table = document.createElement('table');
            table.className = 'stats-table';
            const thead = table.createTHead();
            let headerRow = `<tr><th>Rank</th><th>Player</th>`;
            if (leaderboardInfo.type === 'season') headerRow += `<th>Team</th>`;
            if (leaderboardInfo.type === 'single-season') headerRow += `<th>Season</th>`;
            headerRow += `<th>${stat}</th></tr>`;
            thead.innerHTML = headerRow;
            
            const tbody = table.createTBody();
            let lastPlayer = null;
            let lastRank = 0;
            leaderboard.forEach((p, i) => {
                const rank = i + 1;

                let displayRank;
                if (i > 0 && arePlayersTied(p, lastPlayer)) {
                    displayRank = lastRank;
                } else {
                    displayRank = rank;
                }

                const id = p[isHitting ? 'Hitter ID' : 'Pitcher ID'];
                const playerName = state.players[id] ? state.players[id].currentName : 'Unknown';
                let row = `<tr><td>${displayRank}</td><td class="player-name-cell" data-player-id="${id}" style="cursor: pointer; text-decoration: underline;">${playerName}</td>`;
                if (leaderboardInfo.type === 'season') row += `<td>${p.Team || ''}</td>`;
                if (leaderboardInfo.type === 'single-season') row += `<td>${p.Season.slice(1)}</td>`;
                row += `<td>${formatStat(stat, p[statKey])}</td></tr>`;
                tbody.innerHTML += row;

                lastPlayer = p;
                lastRank = displayRank;
            });

            if (tieInfo) {
                const colspan = thead.rows[0].cells.length;
                tbody.innerHTML += `<tr><td class="tie-info" colspan="${colspan}">${tieInfo.count} players tied with ${formatStat(stat, tieInfo.value)}</td></tr>`;
            }

            seasonCard.appendChild(table);
            gridContainer.appendChild(seasonCard);
        }

        elements.leaderboardsContentDisplay.appendChild(gridContainer);
    };

    const displayScoutingReport = (playerId) => {
        const report = state.scoutingReports[playerId];
        if (!report) {
            elements.statsContentDisplay.innerHTML += `<p>No scouting report available.</p>`;
            return;
        }
        elements.statsContentDisplay.innerHTML += `<h3 class="section-title">Scouting Report</h3>`;

        const mainGrid = document.createElement('div');
        mainGrid.className = 'scouting-report-grid';

        const leftColumn = document.createElement('div');
        leftColumn.className = 'scouting-report-left';

        const rightColumn = document.createElement('div');
        rightColumn.className = 'scouting-report-right';

        // --- Favorite Pitches ---
        if (report.top_5_pitches) {
            const section = document.createElement('div');
            section.className = 'scouting-section';
            const title = document.createElement('h3');
            title.textContent = 'Favorite Pitches';
            section.appendChild(title);

            const pitches = Object.entries(report.top_5_pitches)
                .map(([pitch, count]) => ({ pitch, count }))
                .sort((a, b) => b.count - a.count);

            if (pitches.length > 0) {
                const container = document.createElement('div');
                container.className = 'horizontal-items-container';
                pitches.forEach(p => {
                    const item = document.createElement('div');
                    item.className = 'info-item';
                    const valueDiv = document.createElement('div');
                    valueDiv.className = 'info-item-value';
                    valueDiv.textContent = p.pitch;
                    const labelDiv = document.createElement('div');
                    labelDiv.className = 'info-item-label';
                    labelDiv.textContent = `${p.count}x`;
                    item.appendChild(valueDiv);
                    item.appendChild(labelDiv);
                    container.appendChild(item);
                });
                section.appendChild(container);
            } else {
                section.innerHTML += '<p>No pitch data available.</p>';
            }
            leftColumn.appendChild(section);
        }

        // --- Tendencies ---
        if (report.tendencies) {
            const section = document.createElement('div');
            section.className = 'scouting-section';
            const title = document.createElement('h3');
            title.textContent = 'Tendencies';
            section.appendChild(title);

            const tendencyNameMap = {
                'repeat_percentage': 'Double Up Rate',
                'has_tripled_up': 'Ever Tripled Up?',
                'swing_match_rate': 'Previous Swing Rate',
                'diff_match_rate': 'Previous Difference Rate',
                'meme_percentage': 'Meme Rate'
            };

            const container = document.createElement('div');
            container.className = 'horizontal-items-container';
            for(const [key, value] of Object.entries(report.tendencies)){
                const item = document.createElement('div');
                item.className = 'info-item';
                const valueDiv = document.createElement('div');
                valueDiv.className = 'info-item-value';
                
                let displayValue;
                if (typeof value === 'boolean') {
                    displayValue = value ? 'Yes' : 'No';
                } else {
                    displayValue = `${value}%`;
                }
                valueDiv.textContent = displayValue;

                const labelDiv = document.createElement('div');
                labelDiv.className = 'info-item-label';
                labelDiv.textContent = tendencyNameMap[key] || key.replace(/_/g, ' ');
                item.appendChild(valueDiv);
                item.appendChild(labelDiv);
                container.appendChild(item);
            }
            section.appendChild(container);
            leftColumn.appendChild(section);
        }

        // --- Recent Game Line Graph ---
        if (report.recent_game_info && report.recent_game_info.pitches && report.recent_game_info.pitches.length > 0) {
            const section = document.createElement('div');
            section.className = 'scouting-section';
            
            const game_info = report.recent_game_info;
            const titleText = `${game_info.pitcher_team} ${game_info.season}.${game_info.session} vs. ${game_info.opponent}`;
            
            const title = document.createElement('h3');
            title.textContent = titleText;
            section.appendChild(title);

            const canvas = document.createElement('canvas');
            section.appendChild(canvas);

            new Chart(canvas, {
                type: 'line',
                data: {
                    labels: Array.from({ length: game_info.pitches.length }, (_, i) => i + 1),
                    datasets: [{
                        label: 'Pitch Number',
                        data: game_info.pitches,
                        borderColor: '#FF4500',
                        backgroundColor: 'rgba(255, 69, 0, 0.2)',
                        fill: true,
                        tension: 0.1
                    }]
                },
                options: {
                    scales: {
                        y: { ticks: { color: '#D7DADC' }, grid: { color: '#343536' } },
                        x: { ticks: { color: '#D7DADC' }, grid: { color: '#343536' }, title: { display: true, text: 'Pitch in Sequence' } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
            
            leftColumn.appendChild(section);
        }

        // --- Histograms ---
        if (report.histograms) {
            const section = document.createElement('div');
            section.className = 'scouting-section';

            const sectionHeader = document.createElement('div');
            sectionHeader.className = 'scouting-section-header';

            const title = document.createElement('h3');
            title.textContent = 'Pitch Histograms';
            sectionHeader.appendChild(title);

            const controlsWrapper = document.createElement('div');
            controlsWrapper.className = 'histogram-header-controls';

            const nValueSpan = document.createElement('span');
            nValueSpan.className = 'histogram-n-value';
            controlsWrapper.appendChild(nValueSpan);
            
            const titleMap = {
                'overall': 'All Pitches',
                'first_of_game': 'First Pitch of Game',
                'first_of_inning': 'First Pitch of Inning',
                'risp': 'Pitches with Runners in Scoring Position'
            };

            const select = document.createElement('select');
            select.className = 'histogram-select';

            const situationalGroup = document.createElement('optgroup');
            situationalGroup.label = 'Situational';
            for (const key in report.histograms) {
                const option = document.createElement('option');
                option.value = key;
                option.textContent = titleMap[key] || key.replace(/_/g, ' ');
                situationalGroup.appendChild(option);
            }
            select.appendChild(situationalGroup);

            if (report.conditional_histograms) {
                const conditionalGroup = document.createElement('optgroup');
                conditionalGroup.label = 'Conditional (After...)';
                const sortedKeys = Object.keys(report.conditional_histograms).sort((a, b) => {
                    return parseInt(a.split('_')[1]) - parseInt(b.split('_')[1]);
                });
                for (const key of sortedKeys) {
                    const option = document.createElement('option');
                    option.value = key;
                    let friendlyName = `After ${key.split('_')[1]}`;
                    if (key === 'after_000s') {
                        friendlyName = 'After 0s';
                    }
                    option.textContent = friendlyName;
                    conditionalGroup.appendChild(option);
                }
                select.appendChild(conditionalGroup);
            }

            if (report.season_histograms) {
                const seasonGroup = document.createElement('optgroup');
                seasonGroup.label = 'By Season';
                const sortedSeasons = Object.keys(report.season_histograms).sort((a, b) => {
                    return parseInt(a.slice(1)) - parseInt(b.slice(1));
                });
                for (const season of sortedSeasons) {
                    const option = document.createElement('option');
                    option.value = season;
                    option.textContent = `Season ${season.slice(1)}`;
                    seasonGroup.appendChild(option);
                }
                select.appendChild(seasonGroup);
            }
            
            controlsWrapper.appendChild(select);
            sectionHeader.appendChild(controlsWrapper);
            section.appendChild(sectionHeader);

            const chartWrapper = document.createElement('div');
            chartWrapper.className = 'chart-wrapper';
            section.appendChild(chartWrapper);

            const renderChart = (key) => {
                chartWrapper.innerHTML = '';
                
                let data;
                if (key.startsWith('after_')) {
                    data = report.conditional_histograms[key];
                } else if (key.startsWith('S')) {
                    data = report.season_histograms[key];
                } else {
                    data = report.histograms[key];
                }

                if (!data) {
                    nValueSpan.textContent = '';
                    return;
                }

                const totalN = data.reduce((sum, bin) => sum + bin.count, 0);
                nValueSpan.textContent = `N = ${totalN}`;

                const chartContainer = document.createElement('div');
                chartContainer.className = 'chart-container';

                const chartLabels = data.map(bin => {
                    const lower_bound = parseInt(bin.label.split('-')[0], 10);
                    if (lower_bound === 1) return '0s';
                    return `${Math.floor(lower_bound / 100) * 100}s`;
                });
                const chartCounts = data.map(bin => bin.count);

                const canvas = document.createElement('canvas');
                chartContainer.appendChild(canvas);
                chartWrapper.appendChild(chartContainer);

                new Chart(canvas, {
                    type: 'bar',
                    data: {
                        labels: chartLabels,
                        datasets: [{
                            label: 'Count',
                            data: chartCounts,
                            backgroundColor: 'rgba(255, 69, 0, 0.6)',
                            borderColor: 'rgba(255, 69, 0, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        scales: {
                            y: { beginAtZero: true, ticks: { color: '#D7DADC' }, grid: { color: '#343536' } },
                            x: { ticks: { color: '#D7DADC' }, grid: { display: false } }
                        },
                        plugins: { legend: { display: false } }
                    }
                });
            };

            renderChart(select.value);

            select.addEventListener('change', (event) => {
                renderChart(event.target.value);
            });

            rightColumn.appendChild(section);
        }

        mainGrid.appendChild(leftColumn);
        mainGrid.appendChild(rightColumn);
        elements.statsContentDisplay.appendChild(mainGrid);
    };



    const goToRandomPlayerPage = () => {
        const playerIds = Object.keys(state.players);
        const randomPlayerId = playerIds[Math.floor(Math.random() * playerIds.length)];
        const randomPlayerName = state.players[randomPlayerId].currentName;

        window.location.hash = '#/stats'; // Navigate to player stats view
        elements.playerSearch.value = randomPlayerName;
        elements.playerSuggestions.innerHTML = ''; // Clear any suggestions
        displayPlayerPage(parseInt(randomPlayerId));
    };

    const handlePlayerSearch = (event) => {
        const query = event.target.value.toLowerCase();
        elements.playerSuggestions.innerHTML = '';
        if (query.length < 2) return;

        const suggestions = new Map(); // Use a map to avoid duplicate players

        // Search by name
        for (const [name, id] of state.playerMap.entries()) {
            if (name.toLowerCase().includes(query)) {
                if (!suggestions.has(id)) {
                    suggestions.set(id, state.players[id].currentName);
                }
            }
        }

        // Search by ID
        if (/^-?\d+$/.test(query)) {
            const id = parseInt(query);
            if (state.players[id] && !suggestions.has(id)) {
                suggestions.set(id, state.players[id].currentName);
            }
        }

        let count = 0;
        for (const [id, name] of suggestions) {
            if (count >= 10) break;
            const div = document.createElement('div');
            div.textContent = name;
            div.className = 'suggestion-item';
            div.addEventListener('click', () => {
                elements.playerSearch.value = name;
                elements.playerSuggestions.innerHTML = '';
                displayPlayerPage(id);
            });
            elements.playerSuggestions.appendChild(div);
            count++;
        }
    };

    const populateTeamFilter = () => {
        const teamFilter = elements.leaderboardTeamFilter;
        if (!teamFilter) return;
        const teams = Object.keys(state.teamHistory).sort();
        teams.forEach(team => {
            const option = document.createElement('option');
            option.value = team;
            option.textContent = team;
            teamFilter.appendChild(option);
        });
    };



    const displayPlayerPage = (playerId) => {
        state.currentPlayerId = playerId;
        elements.statsContentDisplay.innerHTML = '';
        const player = state.players[playerId];
        if (!player) return;

        const path = window.location.hash || '#/stats';
        const isScouting = path === '#/scouting';
        const isStats = path === '#/stats';

        const playerName = player.currentName;

        const hittingStats = state.hittingStats.filter(s => s['Hitter ID'] === playerId);
        const pitchingStats = state.pitchingStats.filter(s => s['Pitcher ID'] === playerId);

        // Filter out 'Type' rows from player stat tables
        const filteredHittingStats = hittingStats.filter(s => s.Season !== 'Type');
        const filteredPitchingStats = pitchingStats.filter(s => s.Season !== 'Type');

        let mostRecentTeam = null;
        let mostRecentSeason = null;
        const allStats = [...filteredHittingStats, ...filteredPitchingStats];

        if (allStats.length > 0) {
            const lastSeasonStats = allStats
                .filter(s => s.Season && s.Season.startsWith('S') && !s.is_sub_row)
                .sort((a, b) => parseInt(b.Season.slice(1)) - parseInt(a.Season.slice(1)))[0];
            
            if (lastSeasonStats) {
                mostRecentTeam = lastSeasonStats['Last Team'] || lastSeasonStats['Team'];
                mostRecentSeason = lastSeasonStats.Season;
            }
        }

        let titleHTML = `<h2 class="section-title">${playerName}</h2>`;
        if (mostRecentTeam && mostRecentSeason) {
            const franchiseKey = getFranchiseKeyFromAbbr(mostRecentTeam, mostRecentSeason);
            const logoUrl = getTeamLogoBySeason(franchiseKey, mostRecentSeason);
            if (logoUrl) {
                titleHTML = `<h2 class="section-title"><img src="${logoUrl}" class="player-team-logo"> ${playerName}</h2>`;
            }
        }

        titleHTML += `<p class="player-id-display">Player ID: ${playerId}</p>`;

        if (player.formerNames && player.formerNames.length > 0) {
            titleHTML += `<p class="former-names">Formerly known as: ${player.formerNames.join(', ')}</p>`;
        }

        const playerInfo = state.playerInfo[playerId];
        if (playerInfo) {
            let playerInfoHTML = '';
            if (playerInfo.primary_position && state.typeDefinitions.position && state.typeDefinitions.position[playerInfo.primary_position]) {
                playerInfoHTML += `<p><strong>Position:</strong> ${state.typeDefinitions.position[playerInfo.primary_position]}</p>`;
            }
            if (playerInfo.handedness && state.typeDefinitions.handedness && state.typeDefinitions.handedness[playerInfo.handedness]) {
                playerInfoHTML += `<p><strong>Handedness:</strong> ${state.typeDefinitions.handedness[playerInfo.handedness]}</p>`;
            }

            const primaryPosition = playerInfo.primary_position;

            // Batting type should show for any position other than 'P'
            if (primaryPosition !== 'P' && playerInfo.batting_type && state.typeDefinitions.batting && state.typeDefinitions.batting[playerInfo.batting_type]) {
                playerInfoHTML += `<p><strong>Batting:</strong> ${state.typeDefinitions.batting[playerInfo.batting_type]}</p>`;
            }

            // Pitching type should only show for 'P' and 'PH'
            if ((primaryPosition === 'P' || primaryPosition === 'PH') && playerInfo.pitching_type && state.typeDefinitions.pitching && state.typeDefinitions.pitching[playerInfo.pitching_type]) {
                playerInfoHTML += `<p><strong>Pitching:</strong> ${state.typeDefinitions.pitching[playerInfo.pitching_type]}</p>`;
            }
            
            if (playerInfoHTML) {
                titleHTML += `<div class="player-info">${playerInfoHTML}</div>`;
            }
        }
        elements.statsContentDisplay.innerHTML = titleHTML;

        if (isStats) {
            const lastHittingSeasonNum = Math.max(
                -1,
                ...filteredHittingStats
                    .filter(s => s.Season && !s.Season.startsWith('C') && !s.Season.startsWith('F'))
                    .map(s => parseInt(s.Season.slice(1)))
            );
            const lastPitchingSeasonNum = Math.max(
                -1,
                ...filteredPitchingStats
                    .filter(s => s.Season && !s.Season.startsWith('C') && !s.Season.startsWith('F'))
                    .map(s => parseInt(s.Season.slice(1)))
            );
    
            let primaryRole = 'hitter';
    
            if (lastPitchingSeasonNum > lastHittingSeasonNum) {
                primaryRole = 'pitcher';
            } else if (lastHittingSeasonNum > lastPitchingSeasonNum) {
                primaryRole = 'hitter';
            } else if (lastHittingSeasonNum > 0) { // They are equal and positive, so they played both in the same most recent season.
                const lastSeason = `S${lastHittingSeasonNum}`;
                const recentHitting = filteredHittingStats.find(s => s.Season === lastSeason && !s.is_sub_row);
                const recentPitching = filteredPitchingStats.find(s => s.Season === lastSeason && !s.is_sub_row);
    
                if (recentPitching && recentHitting) {
                    if (recentPitching.G > recentHitting.G) {
                        primaryRole = 'pitcher';
                    } else if (recentPitching.G === recentHitting.G) {
                        if ((recentPitching.BF || 0) > (recentHitting.PA || 0)) {
                            primaryRole = 'pitcher';
                        }
                    }
                } else if (recentPitching) { // Only pitching in the last season
                    primaryRole = 'pitcher';
                }
            } else { // No recent season data, check career data
                const careerHitting = filteredHittingStats.find(s => s.Season === 'Career');
                const careerPitching = filteredPitchingStats.find(s => s.Season === 'Career');
                if (careerPitching && !careerHitting) {
                    primaryRole = 'pitcher';
                } else if (careerPitching && careerHitting) {
                    if (careerPitching.G > careerHitting.G) {
                        primaryRole = 'pitcher';
                    } else if (careerPitching.G === careerHitting.G) {
                        if ((careerPitching.BF || 0) > (careerHitting.PA || 0)) {
                            primaryRole = 'pitcher';
                        }
                    }
                }
            }
    
            const renderHitting = () => {
                if (filteredHittingStats.length > 0) {
                    const franchiseFirstSeason = new Map();
                    const allPlayerSeasonStats = filteredHittingStats.filter(s => s.Season.startsWith('S') && (s.is_sub_row || !s.Team.includes('TM')));

                    for (const stat of allPlayerSeasonStats) {
                        const seasonNum = parseInt(stat.Season.slice(1));
                        const teamAbbr = stat.Team;
                        const franchiseKey = getFranchiseKeyFromAbbr(teamAbbr, stat.Season);

                        if (franchiseKey) {
                            if (!franchiseFirstSeason.has(franchiseKey) || seasonNum < franchiseFirstSeason.get(franchiseKey)) {
                                franchiseFirstSeason.set(franchiseKey, seasonNum);
                            }
                        }
                    }

                    filteredHittingStats.sort((a, b) => {
                        const getScore = (season) => {
                            if (season === 'Franchise') return 3;
                            if (season === 'Career') return 2;
                            return 0;
                        }
                        const scoreA = getScore(a.Season);
                        const scoreB = getScore(b.Season);
                        if (scoreA !== scoreB) {
                            return scoreA - scoreB;
                        }

                        if (a.Season === 'Franchise') {
                            const paA = a.PA || 0;
                            const paB = b.PA || 0;
                            if (paB !== paA) {
                                return paB - paA;
                            }
                            const firstSeasonA = franchiseFirstSeason.get(a.Team) || Infinity;
                            const firstSeasonB = franchiseFirstSeason.get(b.Team) || Infinity;
                            if (firstSeasonA !== firstSeasonB) {
                                return firstSeasonA - firstSeasonB;
                            }
                            return a.Team.localeCompare(b.Team);
                        }

                        if (a.Season === 'Career') {
                            return 0; // Should be only one
                        }

                        // Season rows
                        const seasonA = parseInt(a.Season.slice(1));
                        const seasonB = parseInt(b.Season.slice(1));
                        if (seasonA !== seasonB) {
                            return seasonA - seasonB;
                        }
    
                        const subRowA = a.is_sub_row ? 1 : 0;
                        const subRowB = b.is_sub_row ? 1 : 0;
                        return subRowA - subRowB;
                    });
                    elements.statsContentDisplay.innerHTML += createStatsTable('Batting Stats', filteredHittingStats, STAT_DEFINITIONS, false, true);
                }
            };
    
            const renderPitching = () => {
                if (filteredPitchingStats.length > 0) {
                    const franchiseFirstSeason = new Map();
                    const allPlayerSeasonStats = filteredPitchingStats.filter(s => s.Season.startsWith('S') && (s.is_sub_row || !s.Team.includes('TM')));

                    for (const stat of allPlayerSeasonStats) {
                        const seasonNum = parseInt(stat.Season.slice(1));
                        const teamAbbr = stat.Team;
                        const franchiseKey = getFranchiseKeyFromAbbr(teamAbbr, stat.Season);

                        if (franchiseKey) {
                            if (!franchiseFirstSeason.has(franchiseKey) || seasonNum < franchiseFirstSeason.get(franchiseKey)) {
                                franchiseFirstSeason.set(franchiseKey, seasonNum);
                            }
                        }
                    }

                    filteredPitchingStats.sort((a, b) => {
                        const getScore = (season) => {
                            if (season === 'Franchise') return 3;
                            if (season === 'Career') return 2;
                            return 0;
                        }
                        const scoreA = getScore(a.Season);
                        const scoreB = getScore(b.Season);
                        if (scoreA !== scoreB) {
                            return scoreA - scoreB;
                        }

                        if (a.Season === 'Franchise') {
                            const ipA = a.IP || 0;
                            const ipB = b.IP || 0;
                            if (ipB !== ipA) {
                                return ipB - ipA;
                            }
                            const firstSeasonA = franchiseFirstSeason.get(a.Team) || Infinity;
                            const firstSeasonB = franchiseFirstSeason.get(b.Team) || Infinity;
                            if (firstSeasonA !== firstSeasonB) {
                                return firstSeasonA - firstSeasonB;
                            }
                            return a.Team.localeCompare(b.Team);
                        }

                        if (a.Season === 'Career') {
                            return 0; // Should be only one
                        }

                        // Season rows
                        const seasonA = parseInt(a.Season.slice(1));
                        const seasonB = parseInt(b.Season.slice(1));
                        if (seasonA !== seasonB) {
                            return seasonA - seasonB;
                        }
    
                        const subRowA = a.is_sub_row ? 1 : 0;
                        const subRowB = b.is_sub_row ? 1 : 0;
                        return subRowA - subRowB;
                    });
                    elements.statsContentDisplay.innerHTML += createStatsTable('Pitching Stats', filteredPitchingStats, STAT_DEFINITIONS, true, true);
                }
            };
    
            if (primaryRole === 'pitcher') {
                renderPitching();
                renderHitting();
            } else {
                renderHitting();
                renderPitching();
            }

            elements.statsContentDisplay.querySelectorAll('.stats-table').forEach(makeTableSortable);
        }

        if (isScouting) {
            displayScoutingReport(playerId);
        }
    };

    const makeTableSortable = (table) => {
        const headers = table.querySelectorAll('thead th');
        const groupName = table.previousElementSibling?.textContent;
        const isOpponentStats = groupName === 'Opponent Stats';
        const isHittingTable = groupName?.includes('Batting'); // Changed from Hitting to Batting

        headers.forEach((header, index) => {
            const statName = header.textContent.trim();
            if (['Team'].includes(statName)) return;

            header.style.cursor = 'pointer';

            header.addEventListener('click', () => {
                const tbody = table.querySelector('tbody');
                if (!tbody) return;

                const lowerIsBetterHitting = ['Avg Diff'];
                const lowerIsBetterPitching = ['ERA', 'FIP', 'WHIP', 'H6', 'HR6', 'BB6', 'RE24', 'HR%', 'BB%', 'ERA-'];
                const opponentStatsHighIsBetter = ['SB', 'CS'];

                let isLowerBetter = false;
                if (isOpponentStats) {
                    if (opponentStatsHighIsBetter.includes(statName)) {
                        isLowerBetter = false;
                    } else {
                        isLowerBetter = true;
                    }
                } else if (isHittingTable) {
                    isLowerBetter = lowerIsBetterHitting.includes(statName);
                } else { // Pitching
                    isLowerBetter = lowerIsBetterPitching.includes(statName);
                }

                const currentSortDir = header.dataset.sortDir;
                let nextSortDir;
                const primarySort = isLowerBetter ? 'asc' : 'desc';
                const secondarySort = isLowerBetter ? 'desc' : 'asc';

                if (!currentSortDir) {
                    nextSortDir = primarySort;
                } else if (currentSortDir === primarySort) {
                    nextSortDir = secondarySort;
                } else {
                    nextSortDir = 'default';
                }

                const rows = Array.from(tbody.querySelectorAll('tr'));
                const staticRows = rows.filter(row => row.classList.contains('career-row') || row.classList.contains('franchise-row'));
                const dataRows = rows.filter(row => !row.classList.contains('career-row') && !row.classList.contains('franchise-row'));

                headers.forEach(h => {
                    delete h.dataset.sortDir;
                    const arrow = h.querySelector('.sort-arrow');
                    if (arrow) arrow.remove();
                });

                if (nextSortDir === 'default') {
                    // Sort by Season (index 0) ascending, then by sub-row status, then by original index
                    dataRows.sort((a, b) => {
                        const aText = a.cells[0].textContent;
                        const bText = b.cells[0].textContent;
                        const seasonA = aText ? parseInt(aText.slice(1)) : 0;
                        const seasonB = bText ? parseInt(bText.slice(1)) : 0;
                        
                        if (seasonA !== seasonB) {
                            return seasonA - seasonB;
                        }

                        // If seasons are the same, main row (not a sub-row) comes first
                        const subRowA = a.classList.contains('sub-row') ? 1 : 0;
                        const subRowB = b.classList.contains('sub-row') ? 1 : 0;
                        if (subRowA !== subRowB) {
                            return subRowA - subRowB;
                        }

                        // If seasons and sub-row status are the same, use original index as tie-breaker
                        const originalIndexA = parseInt(a.dataset.originalIndex || '0');
                        const originalIndexB = parseInt(b.dataset.originalIndex || '0');
                        return originalIndexA - originalIndexB;
                    });
                } else {
                    header.dataset.sortDir = nextSortDir;
                    const arrow = document.createElement('span');
                    arrow.className = 'sort-arrow';
                    arrow.innerHTML = nextSortDir === 'asc' ? ' &uarr;' : ' &darr;';
                    header.appendChild(arrow);

                    const isIP = statName === 'IP';

                    dataRows.sort((a, b) => {
                        const aText = a.cells[index].textContent;
                        const bText = b.cells[index].textContent;

                        let aVal, bVal;

                        if (isIP) {
                            const parseIP = (ip) => {
                                if (ip === '-') return -1;
                                const parts = ip.split('.');
                                return parseFloat(parts[0]) + (parseFloat(parts[1] || 0) / 3);
                            };
                            aVal = parseIP(aText);
                            bVal = parseIP(bText);
                        } else {
                            aVal = aText === '-' ? -Infinity : parseFloat(aText);
                            bVal = bText === '-' ? -Infinity : parseFloat(bText);
                        }

                        if (isNaN(aVal)) aVal = -Infinity;
                        if (isNaN(bVal)) bVal = -Infinity;

                        return nextSortDir === 'asc' ? aVal - bVal : bVal - aVal;
                    });
                }

                tbody.innerHTML = '';
                dataRows.forEach(row => tbody.appendChild(row));
                staticRows.forEach(row => tbody.appendChild(row));
            });
        });
    };

    const displayTeamList = (selectedSeason = null) => {
        elements.teamStatsView.innerHTML = ''; // Clear previous content

        const allSeasons = state.seasonsWithStats;
        const currentSeason = selectedSeason || allSeasons[allSeasons.length - 1]; // Default to latest season
                const currentSeasonIndex = allSeasons.indexOf(currentSeason);
        
                const prevSeason = currentSeasonIndex > 0 ? allSeasons[currentSeasonIndex - 1] : null;
                const nextSeason = currentSeasonIndex < allSeasons.length - 1 ? allSeasons[currentSeasonIndex + 1] : null;
        
                let content = `<div class="team-stats-header">
                                <h2 class="section-title">Standings - 
                                    <select id="team-season-select" class="title-season-select">`;
                allSeasons.forEach(season => {
                    const isSelected = season === currentSeason ? 'selected' : '';
                    content += `<option value="${season}" ${isSelected}>Season ${season.slice(1)}</option>`;
                });
                content += `        </select>
                                </h2>
                                <div class="season-nav-buttons">`;
                if (prevSeason) {
                    content += `<a href="#/team-stats?season=${prevSeason}" class="season-nav-button">&lt; Prev Season</a>`;
                }
                if (nextSeason) {
                    content += `<a href="#/team-stats?season=${nextSeason}" class="season-nav-button">Next Season &gt;</a>`;
                }
                content += `    </div>
                            </div>`;

        // Calculate records and standings
        const teamRecords = calculateTeamRecords(currentSeason);
        const standings = getStandings(currentSeason, teamRecords);

        if (Object.keys(standings).length === 0) {
            content += `<p>No standings data available for Season ${currentSeason.slice(1)}.</p>`;
        } else {
            // New container for columns
            content += `<div class="standings-columns">`; // Added
            for (const divisionName in standings) {
                content += `<div class="division-standings-container">`; // Added
                content += `<h3 class="division-title">${divisionName} Division</h3>`;
                content += `<table class="stats-table standings-table">`;
                content += `<thead><tr><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>GB</th></tr></thead>`;
                content += `<tbody>`;
                const divisionTeams = standings[divisionName];
                if (divisionTeams.length > 0) {
                    const leader = divisionTeams[0];
                    divisionTeams.forEach(team => {
                        let gbDisplay;
                        if (team.W === leader.W && team.L === leader.L) {
                            gbDisplay = '-';
                        } else {
                            const gamesBack = ((leader.W - team.W) + (team.L - leader.L)) / 2;
                            gbDisplay = String(gamesBack);
                        }

                        const franchiseKey = getFranchiseKeyFromAbbr(team.teamAbbr, currentSeason); // Get franchise key
                        const teamLogoSrc = getTeamLogoBySeason(franchiseKey, currentSeason);
                        content += `<tr>`;
                        const teamName = getTeamNameBySeason(franchiseKey, currentSeason);
                        content += `<td><span class="team-link" data-team="${encodeURIComponent(franchiseKey)}" data-season="${currentSeason}">`; // Use franchiseKey
                        if (teamLogoSrc) {
                            content += `<img src="${teamLogoSrc}" alt="${team.teamAbbr} logo" class="team-list-logo standings-logo"> `;
                        }
                        content += `${teamName}</span></td>`;
                        content += `<td>${team.W}</td>`;
                        content += `<td>${team.L}</td>`;
                        content += `<td>${team.PCT.toFixed(3).substring(1)}</td>`; // Format PCT
                        content += `<td>${gbDisplay}</td>`;
                        content += `</tr>`;
                    });
                }
                content += `</tbody>`;
                content += `</table>`;
                content += `</div>`; // Added
            }
            content += `</div>`; // Added
        }

        elements.teamStatsView.innerHTML = content;

        // Add event listener for the season select dropdown
        document.getElementById('team-season-select').addEventListener('change', (event) => {
            const newSeason = event.target.value;
            window.location.hash = `#/team-stats?season=${newSeason}`;
        });
    };

    const displayTeamStatsPage = (teamKey, season) => {
        elements.teamStatsView.innerHTML = ''; // Clear previous content

        // More robust defensive check
        if (!state || !state.hittingStats || !state.pitchingStats) {
            console.error("State or data not fully loaded when trying to display team stats.");
            elements.teamStatsView.innerHTML = "<p>Data is still loading or failed to load. Please try again in a moment.</p>";
            return;
        }

        const seasonNum = parseInt(season.slice(1));
        const franchiseEntries = state.teamHistory[teamKey];
        let actualTeamAbbr = teamKey; // Default to the provided teamKey

        if (franchiseEntries) {
            const entry = franchiseEntries.find(e => seasonNum >= e.start && (e.end === Infinity || seasonNum <= e.end));
            if (entry) {
                actualTeamAbbr = entry.abbr;
            }
        }

        const seasonHittingStats = state.hittingStats.filter(s => s.Season === season && s.Team === actualTeamAbbr);
        const seasonPitchingStats = state.pitchingStats.filter(s => s.Season === season && s.Team === actualTeamAbbr);

        // Find previous and next seasons for navigation
        const allSeasons = state.seasonsWithStats.map(s => parseInt(s.slice(1))).sort((a, b) => a - b);
        const currentSeasonIndex = allSeasons.indexOf(seasonNum);

        let prevSeasonNum = null;
        if (franchiseEntries && currentSeasonIndex > 0) {
            for (let i = currentSeasonIndex - 1; i >= 0; i--) {
                const sNum = allSeasons[i];
                if (franchiseEntries.some(e => sNum >= e.start && sNum <= e.end)) {
                    prevSeasonNum = sNum;
                    break;
                }
            }
        }

        let nextSeasonNum = null;
        if (franchiseEntries && currentSeasonIndex < allSeasons.length - 1) {
            for (let i = currentSeasonIndex + 1; i < allSeasons.length; i++) {
                const sNum = allSeasons[i];
                if (franchiseEntries.some(e => sNum >= e.start && sNum <= e.end)) {
                    nextSeasonNum = sNum;
                    break;
                }
            }
        }

        let headerContent = `<div class="team-stats-header">`;
        
        const teamName = getTeamNameBySeason(teamKey, season);
        const teamLogoSrc = getTeamLogoBySeason(teamKey, season);
        let titleHTML = `<h2 class="section-title">`;
        if (teamLogoSrc) {
            titleHTML += `<img src="${teamLogoSrc}" class="player-team-logo"> `;
        }
        titleHTML += `${teamName} - ${season.replace('S','Season ')}</h2>`;
        headerContent += titleHTML;

        let navButtonsHTML = `<div class="season-nav-buttons">`;
        if (prevSeasonNum) {
            navButtonsHTML += `<a href="#/team-stats?season=S${prevSeasonNum}&team=${teamKey}" class="season-nav-button">&lt; Prev Season</a>`;
        }
        if (nextSeasonNum) {
            navButtonsHTML += `<a href="#/team-stats?season=S${nextSeasonNum}&team=${teamKey}" class="season-nav-button">Next Season &gt;</a>`;
        }
        navButtonsHTML += `</div>`;
        
        headerContent += navButtonsHTML;
        headerContent += `</div>`;

        let content = headerContent;

        if (seasonHittingStats.length > 0) {
            const teamHittingTotals = state.teamHittingStats.find(s => s.Season === season && s.Team === actualTeamAbbr);
            content += createTeamStatsTable('Batting Stats', seasonHittingStats, false, teamHittingTotals);
        }
        if (seasonPitchingStats.length > 0) {
            const teamPitchingTotals = state.teamPitchingStats.find(s => s.Season === season && s.Team === actualTeamAbbr);
            content += createTeamStatsTable('Pitching Stats', seasonPitchingStats, true, teamPitchingTotals);
        }

        elements.teamStatsView.innerHTML = content;
        elements.teamStatsView.querySelectorAll('.stats-table').forEach(makeTableSortable);

        // Apply default sorting
        elements.teamStatsView.querySelectorAll('.stats-table').forEach(table => {
            const titleElement = table.previousElementSibling; // This is the h3 element
            if (titleElement) {
                const title = titleElement.textContent;
                let defaultStat = '';
                if (title.includes('Batting Stats')) {
                    defaultStat = 'PA';
                } else if (title.includes('Pitching Stats')) {
                    defaultStat = 'IP';
                }

                if (defaultStat) {
                    const headers = table.querySelectorAll('thead th');
                    headers.forEach(header => {
                        if (header.textContent.trim() === defaultStat) {
                            header.click(); // Simulate a click to sort
                        }
                    });
                }
            }
        });
    };

    const createTeamStatsTable = (title, stats, isPitching, teamTotals) => {
        let html = `<h3>${title}</h3>`;
        const statKeys = isPitching 
            ? STAT_DEFINITIONS.pitching_tables['Standard Pitching']
            : STAT_DEFINITIONS.batting_tables['Standard Batting'];
        
        const headers = ['Player', ...statKeys.filter(s => s !== 'Season' && s !== 'Team')];

        html += '<table class="stats-table">';
        html += '<thead><tr>';
        headers.forEach(stat => {
            const description = STAT_DESCRIPTIONS[stat] || '';
            html += `<th title="${description}">${stat}</th>`;
        });
        html += '</tr></thead>';
        html += '<tbody>';

        stats.sort((a, b) => {
            const aName = state.players[isPitching ? a['Pitcher ID'] : a['Hitter ID']]?.currentName || '';
            const bName = state.players[isPitching ? b['Pitcher ID'] : b['Hitter ID']]?.currentName || '';
            return aName.localeCompare(bName);
        });

        stats.forEach(s => {
            const playerId = isPitching ? s['Pitcher ID'] : s['Hitter ID'];
            const playerName = state.players[playerId]?.currentName || 'Unknown';
            
            html += '<tr>';
            html += `<td><span class="player-link" data-player-id="${playerId}" style="cursor: pointer; text-decoration: underline;">${playerName}</span></td>`;
            
            headers.slice(1).forEach(stat => {
                let statKey = stat;
                if (isPitching) {
                    if (stat === 'SO') statKey = 'K';
                    else if (stat === 'ER') statKey = 'R';
                    else if (stat === 'H6') statKey = 'H/6';
                    else if (stat === 'HR6') statKey = 'HR/6';
                    else if (stat === 'BB6') statKey = 'BB/6';
                    else if (stat === 'SO6') statKey = 'K/6';
                    else if (stat === 'SO/BB') statKey = 'K/BB';
                    else if (stat === 'GB%') statKey = 'GB%_A';
                    else if (stat === 'FB%') statKey = 'FB%_A';
                    else if (stat === 'GB/FB') statKey = 'GB/FB_A';
                    else if (stat === 'BA') statKey = 'BAA';
                    else if (stat === 'OBP') statKey = 'OBPA';
                    else if (stat === 'SLG') statKey = 'SLGA';
                    else if (stat === 'OPS') statKey = 'OPSA';
                    else if (stat === 'BABIP') statKey = 'BABIP_A';
                    else if (stat === 'HR%') statKey = 'HR%_A';
                    else if (stat === 'K%') statKey = 'K%_A';
                    else if (stat === 'BB%') statKey = 'BB%_A';
                    else if (stat === 'SB') statKey = 'SB_A';
                    else if (stat === 'CS') statKey = 'CS_A';
                    else if (stat === 'SB%') statKey = 'SB%_A';
                } else { // Hitting
                    if (stat === 'SO') statKey = 'K';
                    else if (stat === 'BA') statKey = 'AVG';
                }
                let value = s[statKey];

                if (isPitching) {
                    const ip = s.IP || 0;
                    const w = s.W || 0;
                    const l = s.L || 0;

                    if (stat === 'ERA' && ip === 0) {
                        value = '-';
                    } else if (stat === 'W-L%' && (w + l) === 0) {
                        value = '-';
                    }
                } else { // Hitting
                    const ab = s.AB || 0;
                    const pa = s.PA || 0;

                    if (stat === 'BA' && ab === 0) {
                        value = '-';
                    } else if ((['OBP', 'SLG', 'OPS'].includes(stat)) && pa === 0) {
                        value = '-';
                    }
                }

                html += `<td>${formatStat(stat, value)}</td>`;
            });
            html += '</tr>';
        });

        html += '</tbody>';

        if (teamTotals) {
            html += '<tfoot><tr class="career-row">';
            html += '<td><strong>Team Total</strong></td>';
            headers.slice(1).forEach(key => {
                let statKey = key;
                if (isPitching) {
                    if (key === 'SO') statKey = 'K';
                    else if (key === 'ER') statKey = 'R';
                    else if (key === 'H6') statKey = 'H/6';
                    else if (key === 'HR6') statKey = 'HR/6';
                    else if (key === 'BB6') statKey = 'BB/6';
                    else if (key === 'SO6') statKey = 'K/6';
                    else if (key === 'SO/BB') statKey = 'K/BB';
                    else if (key === 'GB%') statKey = 'GB%_A';
                    else if (key === 'FB%') statKey = 'FB%_A';
                    else if (key === 'GB/FB') statKey = 'GB/FB_A';
                    else if (key === 'BA') statKey = 'BAA';
                    else if (key === 'OBP') statKey = 'OBPA';
                    else if (key === 'SLG') statKey = 'SLGA';
                    else if (key === 'OPS') statKey = 'OPSA';
                    else if (key === 'BABIP') statKey = 'BABIP_A';
                    else if (key === 'HR%') statKey = 'HR%_A';
                    else if (key === 'K%') statKey = 'K%_A';
                    else if (key === 'BB%') statKey = 'BB%_A';
                    else if (key === 'SB') statKey = 'SB_A';
                    else if (key === 'CS') statKey = 'CS_A';
                    else if (key === 'SB%') statKey = 'SB%_A';
                } else { // Hitting
                    if (key === 'SO') statKey = 'K';
                    else if (key === 'BA') statKey = 'AVG';
                }
                html += `<td><strong>${formatStat(key, teamTotals[statKey])}</strong></td>`;
            });
            html += '</tr></tfoot>';
        }

        html += '</table>';
        return html;
    };

    const createStatsTable = (title, stats, statDefinitions, isPitching, bySeason = false) => {
        let html = `<h3 class="section-title">${title}</h3>`;
        const statGroups = isPitching ? statDefinitions.pitching_tables : statDefinitions.batting_tables;

        for (const groupName in statGroups) {
            const groupStats = statGroups[groupName];
            html += `<h4>${groupName}</h4>`;
            html += '<table class="stats-table">';
            html += '<thead><tr>';
            groupStats.forEach(stat => {
                const description = STAT_DESCRIPTIONS[stat] || '';
                html += `<th title="${description}">${stat}</th>`;
            });
            html += '</tr></thead>';
            html += '<tbody>';
            const data = bySeason ? stats : [stats];
            data.forEach((s, index) => {
                let rowClass = '';
                if (bySeason && s.Season === 'Career') {
                    rowClass = 'career-row';
                } else if (bySeason && s.Season === 'Franchise') {
                    rowClass = 'franchise-row sub-row';
                }

                if (s.is_sub_row) {
                    rowClass += ' sub-row';
                }
                html += `<tr class="${rowClass}" data-original-index="${index}">`;
                groupStats.forEach(stat => {
                    let statKey = stat;
                    if (isPitching) {
                        if (stat === 'SO') statKey = 'K';
                        else if (stat === 'ER') statKey = 'R';
                        else if (stat === 'H6') statKey = 'H/6';
                        else if (stat === 'HR6') statKey = 'HR/6';
                        else if (stat === 'BB6') statKey = 'BB/6';
                        else if (stat === 'SO6') statKey = 'K/6';
                        else if (stat === 'SO/BB') statKey = 'K/BB';
                        else if (stat === 'GB%') statKey = 'GB%_A';
                        else if (stat === 'FB%') statKey = 'FB%_A';
                        else if (stat === 'GB/FB') statKey = 'GB/FB_A';
                        else if (stat === 'BA') statKey = 'BAA';
                        else if (stat === 'OBP') statKey = 'OBPA';
                        else if (stat === 'SLG') statKey = 'SLGA';
                        else if (stat === 'OPS') statKey = 'OPSA';
                        else if (stat === 'BABIP') statKey = 'BABIP_A';
                        else if (stat === 'HR%') statKey = 'HR%_A';
                        else if (stat === 'K%') statKey = 'K%_A';
                        else if (stat === 'BB%') statKey = 'BB%_A';
                        else if (stat === 'SB') statKey = 'SB_A';
                        else if (stat === 'CS') statKey = 'CS_A';
                        else if (stat === 'SB%') statKey = 'SB%_A';
                    } else { // Hitting
                        if (stat === 'SO') statKey = 'K';
                        else if (stat === 'BA') statKey = 'AVG';
                    }

                    let value; // Declare 'value' here

                    if (stat === 'Season' && s.Season === 'Franchise') {
                        html += `<td></td>`;
                    } else if (stat === 'Team') {
                        value = s.Team || '';
                        const isMultiTeam = /^\d+TM$/.test(value);
                        if (s.Season !== 'Career' && s.Season !== 'Franchise' && value && !isMultiTeam) { // Only make season-specific teams clickable
                            const franchiseKey = getFranchiseKeyFromAbbr(value, s.Season);
                            html += `<td><span class="team-link" data-team="${encodeURIComponent(franchiseKey)}" data-season="${s.Season}" style="cursor: pointer; text-decoration: underline;">${value}</span></td>`;
                        } else {
                            html += `<td>${formatStat(stat, value)}</td>`;
                        }
                    } else {
                        value = s[statKey]; // Assign 'value' here for non-Team stats

                        if (isPitching) {
                            const ip = s.IP || 0;
                            const bb = s.BB || 0;
                            const w = s.W || 0;
                            const l = s.L || 0;
                            const bf = s.BF || 0;
                            const sb_a = s.SB_A || 0;
                            const cs_a = s.CS_A || 0;

                            if (groupName === 'Opponent Stats') {
                                if ((['BA', 'OBP', 'SLG', 'OPS', 'BABIP'].includes(stat)) && bf === 0) {
                                    value = '-';
                                } else if (stat === 'SB%' && (sb_a + cs_a) === 0) {
                                    value = '-';
                                }
                            } else {
                                if ((['ERA', 'FIP', 'WHIP', 'H6', 'HR6', 'BB6', 'SO6'].includes(stat)) && ip === 0) {
                                    value = '-';
                                } else if (stat === 'SO/BB' && bb === 0) {
                                    value = '-';
                                } else if (stat === 'W-L%' && (w + l) === 0) {
                                    value = '-';
                                } else if ((['HR%', 'K%', 'BB%', 'GB%', 'FB%', 'GB/FB'].includes(stat)) && bf === 0) {
                                    value = '-';
                                }
                            }
                        } else { // Hitting
                            const ab = s.AB || 0;
                            const pa = s.PA || 0;
                            const sb = s.SB || 0;
                            const cs = s.CS || 0;

                            if ((['BA', 'ISO', 'BABIP', 'OPS+', 'SLG', 'OPS'].includes(stat)) && ab === 0) {
                                value = '-';
                            } else if ((['OBP', 'HR%', 'SO%', 'BB%', 'GB%', 'FB%', 'GB/FB'].includes(stat)) && pa === 0) {
                                value = '-';
                            } else if (stat === 'SB%' && (sb + cs) === 0) {
                                value = '-';
                            }
                        }

                        let cellHTML = `<td>${formatStat(stat, value)}</td>`;
                        if (stat === 'Type' && value) {
                            const typeCategory = isPitching ? 'pitching' : 'batting';
                            if (state.typeDefinitions[typeCategory] && state.typeDefinitions[typeCategory][value]) {
                                cellHTML = `<td title="${state.typeDefinitions[typeCategory][value]}">${formatStat(stat, value)}</td>`;
                            }
                        }
                        html += cellHTML;
                    }
                });
                html += '</tr>';
            });
            html += '</tbody></table>';
        }
        return html;
    };
                    
    const formatStat = (stat, value) => {
        if (value === undefined || value === null) return '-';
        if (typeof value === 'number') {
            if (['AVG', 'OBP', 'SLG', 'OPS', 'ISO', 'BA', 'BAA', 'OBPA', 'SLGA', 'OPSA', 'BABIP', 'BABIP_A', 'W-L%'].includes(stat)) {
                const formatted = value.toFixed(3);
                if (formatted.startsWith('0.')) {
                    return formatted.substring(1);
                }
                return formatted;
            }
            if (['ERA', 'WHIP', 'FIP', 'H/6', 'HR/6', 'BB/6', 'K/6', 'K/BB', 'GB/FB', 'GB/FB_A'].includes(stat)) {
                return value.toFixed(2);
            }
            if (['H6', 'HR6', 'BB6', 'SO6', 'SO/BB'].includes(stat)) {
                return value.toFixed(1);
            }
            if (stat === 'IP') {
                const innings = Math.floor(value);
                const outs = Math.round((value - innings) * 3);
                if (outs === 3) {
                    return (innings + 1).toFixed(1);
                }
                return `${innings}.${outs}`;
            }
            if (['WAR', 'RE24', 'WPA', 'Avg Diff'].includes(stat)) {
                return value.toFixed(2);
            }
            if (stat.includes('%')) {
                return (value * 100).toFixed(1);
            }
            return Math.round(value);
        }
        return value;
    };

    const calculateTeamRecords = (season) => {
        const teamRecords = {};
        const seasonPitchingStats = state.pitchingStats.filter(s => s.Season === season);
        const totalGamesInSeason = state.seasons[season] || 0; // This is now confirmed as totalGamesPlayedByTeam

        // Initialize records for all teams that played in this season
        const teamsInSeason = [...new Set(seasonPitchingStats.map(s => s.Team))];
        teamsInSeason.forEach(teamAbbr => {
            teamRecords[teamAbbr] = { W: 0, L: 0, T: 0, PCT: 0 };
        });

        seasonPitchingStats.forEach(stat => {
            const teamAbbr = stat.Team;
            if (teamRecords[teamAbbr]) {
                const wins = stat.W || 0;
                const losses = stat.L || 0;
                teamRecords[teamAbbr].W += wins;
                teamRecords[teamAbbr].L += losses;
            }
        });

        // Calculate Ties and PCT
        for (const teamAbbr in teamRecords) {
            const record = teamRecords[teamAbbr];
            const gamesPlayedByTeam = record.W + record.L; // Sum of pitcher W+L
            record.T = totalGamesInSeason - gamesPlayedByTeam; // Ties calculation
            if (record.T < 0) record.T = 0; // Ensure ties are not negative

            if (record.W + record.L > 0) {
                record.PCT = record.W / (record.W + record.L);
            } else {
                record.PCT = 0;
            }
        }
        return teamRecords;
    };

    const getStandings = (season, teamRecords) => {
        const standings = {};
        const divisionsForSeason = getDivisionsForSeason(season); // Use helper

        if (!divisionsForSeason) {
            console.warn(`No division data found for season ${season}`);
            return {};
        }

        for (const divisionName in divisionsForSeason) {
            const teamsInDivision = divisionsForSeason[divisionName];
            const divisionStandings = [];

            teamsInDivision.forEach(teamAbbr => {
                const record = teamRecords[teamAbbr];
                if (record) {
                    divisionStandings.push({ teamAbbr, ...record });
                } else {
                    // Team exists in division but no record found for season (e.g., new team)
                    divisionStandings.push({ teamAbbr, W: 0, L: 0, T: 0, PCT: 0 });
                }
            });

            // Sort teams within the division: highest PCT first
            divisionStandings.sort((a, b) => b.PCT - a.PCT);
            standings[divisionName] = divisionStandings;
        }
        return standings;
    };

    const getDivisionsForSeason = (season) => {
        let divisions = state.divisions[season];
        // If the value is a string, it's a reference to another season
        if (typeof divisions === 'string') {
            return state.divisions[divisions]; // Resolve the reference
        }
        return divisions;
    };

    const getFranchiseKeyFromAbbr = (abbr, season) => {
        const seasonNum = parseInt(season.slice(1));
        for (const franchiseKey in state.teamHistory) {
            const entries = state.teamHistory[franchiseKey];
            if (entries.some(entry => entry.abbr === abbr && seasonNum >= entry.start && (entry.end === 9999 || seasonNum <= entry.end))) {
                return franchiseKey;
            }
        }
        return abbr; // Fallback if not found, assume abbr is the franchise key
    };

    const getTeamNameBySeason = (franchiseKey, season) => {
        const seasonNum = parseInt(season.slice(1));
        const teamNameEntries = state.teamHistory[franchiseKey];
        if (teamNameEntries) {
            const entry = teamNameEntries.find(e => seasonNum >= e.start && (e.end === 9999 || seasonNum <= e.end));
            if (entry) {
                return entry.name;
            }
        }
        return franchiseKey; // Fallback to franchise key
    };

const getTeamLogoBySeason = (franchiseKey, season) => {
    if (!franchiseKey || !season) return null;
    const seasonNum = parseInt(season.slice(1));
    if (isNaN(seasonNum)) return null;

    const franchise = state.teamHistory[franchiseKey];
    if (!franchise) return null;

    const teamInfo = franchise.find(t => seasonNum >= t.start && seasonNum <= t.end);
    if (!teamInfo) return null;

    const isLightMode = document.documentElement.classList.contains('light-mode');
    return isLightMode ? teamInfo.logo_light : teamInfo.logo_dark;
};
                    
    loadData();
});