# MLR Reference

This repository contains a suite of Python scripts designed for analyzing and viewing statistics from the MLR (Major League Redditball). It allows users to load game data from Google Sheets, process it, and generate detailed player statistics, leaderboards, team stats, and a glossary of terms.

## Web Application Interface

This project now includes a web-based interface to view all player stats, leaderboards, team statistics, and a glossary in a user-friendly format.

### Features:
- **Player Stats:** Comprehensive hitting and pitching statistics for individual players, including career and seasonal breakdowns.
- **Team Stats:** View team standings and individual player statistics per team for each season.
- **Leaderboards:** Dynamic leaderboards for various batting and pitching statistics, with filters for season and team.
- **Glossary:** Definitions and explanations for various baseball statistics and terms, including run expectancy matrices.

### Application Pages
The web application provides several pages to explore the data:
- **Home (`#/home`):** A landing page that welcomes users and showcases featured players and teams.
- **Player Stats (`#/stats`):** A searchable page for individual player statistics, showing detailed batting and pitching data.
- **Team Stats (`#/team-stats`):** Displays season-by-season standings and allows drilling down into team-specific stats.
- **Leaderboards (`#/leaderboards`):** Provides all-time and single-season leaderboards for a wide variety of statistical categories.
- **Glossary (`#/glossary`):** A reference for advanced stats and terminology used in the application.

### Running the Web App

1.  **Generate the Data:**
    First, run the data generation script from the root directory. This script processes all the raw data and creates the JSON files needed by the web app.
    ```bash
    python scripts/generate_web_data.py
    ```

2.  **Start the Web Server:**
    Navigate to the `docs` directory and start a local web server. The simplest way is to use Python's built-in module.
    ```bash
    cd docs
    python -m http.server
    ```

3.  **View the App:**
    Open your web browser and navigate to `http://localhost:8000` (or the address shown in your terminal).

### Deploying to GitHub Pages

Since the web application is built with static files (HTML, CSS, JS), it can be easily hosted on GitHub Pages.

1.  Push the entire project repository to GitHub.
2.  In your repository's settings, go to the "Pages" section.
3.  Configure the source to deploy from the `/docs` folder on your main branch.

## Scripts Overview

- **`scripts/data_loader.py`**: Handles the loading of season data from Google Sheets URLs listed in `data/gamelogs.txt`.
- **`scripts/game_processing.py`**: Contains the core logic for simulating game play-by-play, determining pitching decisions (Win, Loss, Save, Hold), and calculating advanced metrics.
- **`scripts/generate_web_data.py`**: The primary script for processing all raw game data, calculating comprehensive player and team statistics (including OPS+, ERA+, FIP, WAR, RE24), and exporting all necessary data into JSON files for the web application. This script also handles player ID reconciliation, stat corrections for pinch runners and multi-steals, and generates run expectancy matrices.

## Maintenance Information

The site requires maintenance at the beginning of seasons.

- **`data/gamelogs.txt`** needs to be updated to include the new season. A new row with the format {season}*tab*{number_of_sessions}*tab*{gamelog_url} should be added to the file.
- **`docs/data/divisions.json`** needs to be updated to include the new season.
- **`docs/data/team_history.json`** needs to be updated if a franchise changes its name, abbreviation, or logo. This will also need to be updated if teams are added or removed from the league.
- **`scripts/game_processing.py`** needs to be updated if a logical change has been made to the game rules. The `_simulate_play` function tracks the resulting base-out state of outcomes. This is a fairly complex change. Logical changes are made infrequently, the most recent being the addition of lineouts. Changes that don't affect logic (e.g. changes to player types) can be ignored. This file only needs to be updated if a new rule redefines how runners move in a certain situation.