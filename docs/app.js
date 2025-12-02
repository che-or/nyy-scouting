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

    const createHistogramSection = (titleText, situationalHistograms, conditionalHistograms, seasonHistograms, chartLabelStyle, conditionalAfterDeltaHistograms) => {
        const section = document.createElement('div');
        section.className = 'scouting-section';
    
        const sectionHeader = document.createElement('div');
        sectionHeader.className = 'scouting-section-header';
    
        const title = document.createElement('h3');
        title.textContent = titleText;
        sectionHeader.appendChild(title);
    
        const controlsWrapper = document.createElement('div');
        controlsWrapper.className = 'histogram-header-controls';
    
        const nValueSpan = document.createElement('span');
        nValueSpan.className = 'histogram-n-value';
        controlsWrapper.appendChild(nValueSpan);
    
        const select = document.createElement('select');
        select.className = 'histogram-select';
    
        if (situationalHistograms && Object.keys(situationalHistograms).length > 0) {
            const situationalGroup = document.createElement('optgroup');
            situationalGroup.label = 'Situational';
            
            let situationalTitleMap = {
                'overall': 'All Pitches',
                'first_of_game': 'First Pitch of Game',
                'first_of_inning': 'First Pitch of Inning',
                'risp': 'Pitches with Runners in Scoring Position',
            };
            if (chartLabelStyle === 'delta') {
                situationalTitleMap = {
                    'overall': 'All Pitch Deltas',
                }
            }

            for (const key in situationalHistograms) {
                const option = document.createElement('option');
                option.value = key;
                option.textContent = situationalTitleMap[key] || key.replace(/_/g, ' ');
                situationalGroup.appendChild(option);
            }
            select.appendChild(situationalGroup);
        }
        
        if (conditionalHistograms && Object.keys(conditionalHistograms).length > 0) {
            const conditionalGroup = document.createElement('optgroup');
            conditionalGroup.label = 'Conditional (After Pitch)';
            const sortedKeys = Object.keys(conditionalHistograms).sort((a, b) => {
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

        if (conditionalAfterDeltaHistograms && Object.keys(conditionalAfterDeltaHistograms).length > 0) {
            const conditionalGroup = document.createElement('optgroup');
            conditionalGroup.label = 'Conditional (After Delta)';
            const sortedKeys = Object.keys(conditionalAfterDeltaHistograms).sort((a, b) => {
                const a_val = parseInt(a.split('_')[2].split('-')[0]);
                const b_val = parseInt(b.split('_')[2].split('-')[0]);
                return a_val - b_val;
            });
            for (const key of sortedKeys) {
                const option = document.createElement('option');
                option.value = key;
                option.textContent = `After ${key.split('_')[2]}`;
                conditionalGroup.appendChild(option);
            }
            select.appendChild(conditionalGroup);
        }
    
        if (seasonHistograms && Object.keys(seasonHistograms).length > 0) {
            const seasonGroup = document.createElement('optgroup');
            seasonGroup.label = 'By Season';
            const sortedSeasons = Object.keys(seasonHistograms).sort((a, b) => {
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
            if (key.startsWith('after_delta_')) {
                data = conditionalAfterDeltaHistograms[key];
            } else if (key.startsWith('after_')) {
                data = conditionalHistograms[key];
            } else if (key.startsWith('S')) {
                data = seasonHistograms[key];
            } else {
                data = situationalHistograms[key];
            }
    
            if (!data) {
                nValueSpan.textContent = '';
                return;
            }
    
            const totalN = data.reduce((sum, bin) => sum + bin.count, 0);
            nValueSpan.textContent = `N = ${totalN}`;
    
            const chartContainer = document.createElement('div');
            chartContainer.className = 'chart-container';
    
            let chartLabels;
            if (chartLabelStyle === 'delta') {
                chartLabels = data.map(bin => bin.label);
            } else {
                chartLabels = data.map(bin => {
                    const lower_bound = parseInt(bin.label.split('-')[0], 10);
                    if (lower_bound === 1) return '0s';
                    return `${Math.floor(lower_bound / 100) * 100}s`;
                });
            }
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
    
        if(select.options.length > 0){
            renderChart(select.value);
        }

        select.addEventListener('change', (event) => {
            renderChart(event.target.value);
        });
    
        return section;
    }

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
        rightColumn.style.display = 'flex';
        rightColumn.style.flexDirection = 'column';
        rightColumn.style.gap = '20px';

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

        // --- Recent Games Pitch Chart ---
        if (report.recent_games_info && report.recent_games_info.length > 0) {
            const section = document.createElement('div');
            section.className = 'scouting-section';
            
            const header = document.createElement('div');
            header.className = 'scouting-section-header';
            
            const title = document.createElement('h3');
            title.textContent = 'Recent Games - Pitches';
            header.appendChild(title);

            const controls = document.createElement('div');
            controls.className = 'histogram-header-controls';

            const select = document.createElement('select');
            select.className = 'histogram-select';
            report.recent_games_info.forEach((game, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = `${game.season}.${game.session} vs ${game.opponent}`;
                select.appendChild(option);
            });
            controls.appendChild(select);
            header.appendChild(controls);
            section.appendChild(header);

            const pitchChartContainer = document.createElement('div');
            const pitchCanvas = document.createElement('canvas');
            pitchChartContainer.appendChild(pitchCanvas);
            section.appendChild(pitchChartContainer);

            let pitchChart;

            const renderPitchChart = (gameIndex) => {
                const game = report.recent_games_info[gameIndex];

                if (pitchChart) pitchChart.destroy();
                pitchChart = new Chart(pitchCanvas, {
                    type: 'line',
                    data: {
                        labels: Array.from({ length: game.pitches.length }, (_, i) => i + 1),
                        datasets: [{
                            label: 'Pitch Number',
                            data: game.pitches,
                            borderColor: '#FF4500',
                            backgroundColor: 'rgba(255, 69, 0, 0.2)',
                            fill: true,
                            tension: 0.1
                        }]
                    },
                    options: {
                        scales: {
                            y: { min: 0, max: 1000, ticks: { color: '#D7DADC' }, grid: { color: '#343536' } },
                            x: { ticks: { color: '#D7DADC' }, grid: { color: '#343536' }, title: { display: true, text: 'Pitch in Sequence' } }
                        },
                        plugins: { legend: { display: false } }
                    }
                });
            };

            renderPitchChart(0);
            select.addEventListener('change', (e) => renderPitchChart(e.target.value));
            
            leftColumn.appendChild(section);
        }

        // --- Recent Games Delta Chart ---
        if (report.recent_games_info && report.recent_games_info.length > 0) {
            const section = document.createElement('div');
            section.className = 'scouting-section';
            
            const header = document.createElement('div');
            header.className = 'scouting-section-header';
            
            const title = document.createElement('h3');
            title.textContent = 'Recent Games - Deltas';
            header.appendChild(title);

            const controls = document.createElement('div');
            controls.className = 'histogram-header-controls';

            const select = document.createElement('select');
            select.className = 'histogram-select';
            report.recent_games_info.forEach((game, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = `${game.season}.${game.session} vs ${game.opponent}`;
                select.appendChild(option);
            });
            controls.appendChild(select);

            const absLabel = document.createElement('label');
            const absCheckbox = document.createElement('input');
            absCheckbox.type = 'checkbox';
            absLabel.appendChild(absCheckbox);
            absLabel.append(' Absolute Value');



            header.appendChild(controls);
            section.appendChild(header);

            const deltaChartContainer = document.createElement('div');
            const deltaCanvas = document.createElement('canvas');
            deltaChartContainer.appendChild(deltaCanvas);
            section.appendChild(deltaChartContainer);

            // Container for the absolute value checkbox, placed below the chart
            const absCheckboxContainer = document.createElement('div');
            absCheckboxContainer.className = 'abs-checkbox-container'; // Add a class for styling
            absCheckboxContainer.appendChild(absLabel); // absLabel already contains absCheckbox

            section.appendChild(absCheckboxContainer);



            let deltaChart;

            const renderDeltaChart = () => {
                const gameIndex = select.value;
                const game = report.recent_games_info[gameIndex];
                const useAbs = absCheckbox.checked;
                const deltaData = useAbs ? game.deltas.map(Math.abs) : game.deltas;
                
                if (deltaChart) deltaChart.destroy();
                deltaChart = new Chart(deltaCanvas, {
                    type: 'line',
                    data: {
                        labels: Array.from({ length: game.deltas.length }, (_, i) => i + 1),
                        datasets: [{
                            label: 'Pitch Delta',
                            data: deltaData,
                            borderColor: '#FF4500',
                            backgroundColor: 'rgba(255, 69, 0, 0.2)',
                            fill: true,
                            tension: 0.1
                        }]
                    },
                    options: {
                        scales: {
                            y: { min: useAbs ? 0 : -500, max: 500, ticks: { color: '#D7DADC' }, grid: { color: '#343536' } },
                            x: { ticks: { color: '#D7DADC' }, grid: { color: '#343536' }, title: { display: true, text: 'Delta in Sequence' } }
                        },
                        plugins: { legend: { display: false } }
                    }
                });
            };
            
            renderDeltaChart();
            select.addEventListener('change', renderDeltaChart);
            absCheckbox.addEventListener('change', renderDeltaChart);
            
            leftColumn.appendChild(section);
        }


        // --- Histograms ---
        if (report.histograms || report.conditional_histograms || report.season_histograms) {
            const histSection = createHistogramSection('Pitch Histograms', report.histograms, report.conditional_histograms, report.season_histograms, 'pitch', null);
            rightColumn.appendChild(histSection);
        }
        
        if (report.delta_histograms || report.conditional_delta_histograms || report.season_delta_histograms) {
            const deltaHistSection = createHistogramSection('Pitch Delta Histograms', report.delta_histograms, report.conditional_delta_histograms, report.season_delta_histograms, 'delta', report.conditional_after_delta_histograms);
            rightColumn.appendChild(deltaHistSection);
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