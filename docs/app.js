document.addEventListener('DOMContentLoaded', () => {
    const API = {
        players: './data/player_id_map.json',
        scouting: './data/scouting_reports.json',
        teamHistory: './data/team_history.json',
        playerInfo: './data/player_info.json',
        typeDefinitions: './data/type_definitions.json'
    };

    const state = {
        players: {},
        scoutingReports: {},
        teamHistory: {},
        playerInfo: {},
        typeDefinitions: {},
        playerMap: new Map(),
        currentPlayerId: null,
    };

    const elements = {
        loader: document.getElementById('loader'),
        app: document.getElementById('app'),
        statsView: document.getElementById('stats-view'),
        playerSearch: document.getElementById('player-search'),
        playerSuggestions: document.getElementById('player-suggestions'),
        statsContentDisplay: document.getElementById('stats-content-display'),
        themeSwitch: document.getElementById('theme-switch-input'),
        welcomeScreen: document.getElementById('welcome-screen'),
        welcomeLogo: document.getElementById('welcome-logo'),
        continueButton: document.getElementById('continue-button')
    };

    const loadData = async () => {
        try {
            const [players, scouting, teamHistory, playerInfo, typeDefinitions] = await Promise.all([
                fetch(API.players).then(res => res.json()),
                fetch(API.scouting).then(res => res.json()),
                fetch(API.teamHistory).then(res => res.json()),
                fetch(API.playerInfo).then(res => res.json()),
                fetch(API.typeDefinitions).then(res => res.json())
            ]);

            state.players = players;
            state.scoutingReports = scouting;
            state.teamHistory = teamHistory;
            state.playerInfo = playerInfo;
            state.typeDefinitions = typeDefinitions;

            state.playerMap = new Map();
            for (const id in players) {
                const player = players[id];
                const playerId = parseInt(id);

                const addNameToMap = (name) => {
                    const lowerCaseName = name.toLowerCase();
                    if (!state.playerMap.has(lowerCaseName)) {
                        state.playerMap.set(lowerCaseName, []);
                    }
                    const ids = state.playerMap.get(lowerCaseName);
                    if (!ids.includes(playerId)) {
                        ids.push(playerId);
                    }
                };

                addNameToMap(player.currentName);
                if (player.formerNames) {
                    player.formerNames.forEach(addNameToMap);
                }
            }

            elements.loader.style.display = 'none';
            
            initializeApp();
        } catch (error) {
            console.error("Failed to load data:", error);
            elements.loader.innerHTML = "<p>Failed to load data. Please refresh the page.</p>";
        }
    };
    
    const showWelcomeScreen = (isLightMode) => {
        elements.welcomeLogo.src = isLightMode ? './img/logos/NYY_light.svg' : './img/logos/NYY.svg';
        elements.welcomeScreen.style.display = 'block';
    }

    const updateView = () => {
        window.scrollTo(0, 0);
        
        elements.statsView.style.display = 'block';

        if (state.currentPlayerId) {
            displayPlayerPage(state.currentPlayerId);
        } else {
            elements.statsContentDisplay.innerHTML = '<p>Search for a player to see their scouting report.</p>';
        }
    };

    const initializeApp = () => {
        window.addEventListener('hashchange', updateView);

        const themeSwitch = elements.themeSwitch;
        const currentTheme = localStorage.getItem('theme');

        function setTheme(theme) {
            let isLightMode = false;
            if (theme === 'light-mode') {
                document.documentElement.classList.add('light-mode');
                themeSwitch.checked = true;
                isLightMode = true;
            } else {
                document.documentElement.classList.remove('light-mode');
                themeSwitch.checked = false;
            }
            return isLightMode;
        }

        const isLightMode = setTheme(currentTheme || 'dark-mode');
        showWelcomeScreen(isLightMode);

        themeSwitch.addEventListener('change', () => {
            let isLightMode;
            if (themeSwitch.checked) {
                document.documentElement.classList.add('light-mode');
                localStorage.setItem('theme', 'light-mode');
                isLightMode = true;
            } else {
                document.documentElement.classList.remove('light-mode');
                localStorage.setItem('theme', 'dark-mode');
                isLightMode = false;
            }
            if(elements.welcomeScreen.style.display !== 'none'){
                showWelcomeScreen(isLightMode);
            } else {
                updateView();
            }
        });
        
        elements.continueButton.addEventListener('click', () => {
            elements.welcomeScreen.style.display = 'none';
            elements.app.style.display = 'block';
            updateView(); 
        });
        
        elements.playerSearch.addEventListener('input', handlePlayerSearch);

        elements.app.addEventListener('click', (event) => {
            const playerLink = event.target.closest('.player-link');
            if (playerLink) {
                const playerId = parseInt(playerLink.dataset.playerId, 10);
                if (!isNaN(playerId)) {
                    const playerName = state.players[playerId].currentName;
                    window.location.hash = '#/scouting'; // Go to player stats view
                    elements.playerSearch.value = playerName;
                    elements.playerSuggestions.innerHTML = '';
                    elements.playerSuggestions.style.display = 'none';
                    displayPlayerPage(playerId);
                }
            }
        });
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

    const handlePlayerSearch = (event) => {
        const query = event.target.value.toLowerCase();
        elements.playerSuggestions.innerHTML = '';

        const matchingIds = new Set();

        if (/^\d+$/.test(query)) {
            const id = parseInt(query);
            if (state.players[id]) {
                matchingIds.add(id);
            }
        }

        if (query.length >= 2) {
            for (const [name, ids] of state.playerMap.entries()) {
                if (name.includes(query)) {
                    ids.forEach(id => matchingIds.add(id));
                }
            }
        }
        
        if (matchingIds.size === 0) {
            elements.playerSuggestions.style.display = 'none';
            return;
        }
        
        const nameToIds = new Map();
        matchingIds.forEach(id => {
            const currentName = state.players[id].currentName;
            if (!nameToIds.has(currentName)) {
                nameToIds.set(currentName, []);
            }
            nameToIds.get(currentName).push(id);
        });

        elements.playerSuggestions.style.display = 'block';
        let count = 0;

        for (const id of matchingIds) {
            if (count >= 10) break;
            
            const currentName = state.players[id].currentName;
            let suggestionText = currentName;

            if (nameToIds.get(currentName).length > 1) {
                suggestionText += ` (#${id})`;
            }

            const div = document.createElement('div');
            div.textContent = suggestionText;
            div.className = 'suggestion-item';
            div.addEventListener('click', () => {
                elements.playerSearch.value = currentName;
                elements.playerSuggestions.innerHTML = '';
                elements.playerSuggestions.style.display = 'none';
                displayPlayerPage(id);
            });
            elements.playerSuggestions.appendChild(div);
            count++;
        }
    };

    const displayPlayerPage = (playerId) => {
        state.currentPlayerId = playerId;
        elements.statsContentDisplay.innerHTML = '';
        const player = state.players[playerId];
        if (!player) return;

        const playerName = player.currentName;
        const playerInfo = state.playerInfo[playerId];

        let mostRecentTeam = null;
        let mostRecentSeason = null;

        if(playerInfo && playerInfo.last_team && playerInfo.last_season){
            mostRecentTeam = playerInfo.last_team;
            mostRecentSeason = playerInfo.last_season;
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
        
        if (playerInfo) {
            let playerInfoHTML = '';
            if (playerInfo.primary_position && state.typeDefinitions.position && state.typeDefinitions.position[playerInfo.primary_position]) {
                playerInfoHTML += `<p><strong>Position:</strong> ${state.typeDefinitions.position[playerInfo.primary_position]}</p>`;
            }
            if (playerInfo.handedness && state.typeDefinitions.handedness && state.typeDefinitions.handedness[playerInfo.handedness]) {
                playerInfoHTML += `<p><strong>Handedness:</strong> ${state.typeDefinitions.handedness[playerInfo.handedness]}</p>`;
            }

            const primaryPosition = playerInfo.primary_position;

            if (primaryPosition !== 'P' && playerInfo.batting_type && state.typeDefinitions.batting && state.typeDefinitions.batting[playerInfo.batting_type]) {
                playerInfoHTML += `<p><strong>Batting:</strong> ${state.typeDefinitions.batting[playerInfo.batting_type]}</p>`;
            }

            if ((primaryPosition === 'P' || primaryPosition === 'PH') && playerInfo.pitching_type && state.typeDefinitions.pitching && state.typeDefinitions.pitching[playerInfo.pitching_type]) {
                playerInfoHTML += `<p><strong>Pitching:</strong> ${state.typeDefinitions.pitching[playerInfo.pitching_type]}</p>`;
            }
            
            if (playerInfoHTML) {
                titleHTML += `<div class="player-info">${playerInfoHTML}</div>`;
            }
        }
        elements.statsContentDisplay.innerHTML = titleHTML;

        displayScoutingReport(playerId);
    };

    const getFranchiseKeyFromAbbr = (abbr, season) => {
        const seasonNum = parseInt(season.slice(1));
        for (const franchiseKey in state.teamHistory) {
            const entries = state.teamHistory[franchiseKey];
            if (entries.some(entry => entry.abbr === abbr && seasonNum >= entry.start && (entry.end === 9999 || seasonNum <= entry.end))) {
                return franchiseKey;
            }
        }
        return abbr; 
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