# MLR Scouting Endpoint

This repository contains a simplified set of Python scripts and a web interface designed solely for generating and viewing player scouting reports from MLR (Major League Redditball) game data. It focuses on processing raw game data to create detailed scouting profiles for pitchers.

## Web Application Interface

This project now includes a web-based interface to view player scouting reports.

### Features:
-   **Player Scouting Reports:** Detailed scouting information for individual pitchers, including favorite pitches, tendencies, recent game data, and pitch histograms.

### Running the Web App

1.  **Generate the Data:**
    First, run the data generation script from the root directory. This script processes all the raw game data and creates the JSON files needed by the web app for scouting reports.
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
    Open your web browser and navigate to `http://localhost:8000` (or the address shown in your terminal). The application will load the scouting interface. You can search for players by name or ID to view their scouting reports.

### Deploying to GitHub Pages

Since the web application is built with static files (HTML, CSS, JS), it can be easily hosted on GitHub Pages.

1.  Push the entire project repository to GitHub.
2.  In your repository's settings, go to the "Pages" section.
3.  Configure the source to deploy from the `/docs` folder on your main branch.

## Scripts Overview

-   **`scripts/data_loader.py`**: Handles the loading of season data from Google Sheets URLs listed in `data/gamelogs.txt` and player type data from `data/player_types.txt`.
-   **`scripts/gamelog_corrections.py`**: Contains functions to apply manual corrections to raw gamelog data for known errors.
-   **`scripts/generate_web_data.py`**: The primary script for processing all raw game data, reconciling player IDs, and generating `player_id_map.json`, `player_info.json`, and `scouting_reports.json` for the web application.
