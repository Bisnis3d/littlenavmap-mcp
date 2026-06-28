# Little Navmap MCP Server

An MCP (Model Context Protocol) server that exposes [Little Navmap](https://albar965.github.io/littlenavmap.html) as tools for Claude Desktop and other MCP-compatible clients.

Ask Claude things like:
- *"What are the runways and frequencies at LEMD?"*
- *"Show me all VORs and NDBs between lat 40-42, lon -5 to -3"*
- *"What's the active flight plan in Little Navmap?"*
- *"What's the current aircraft position and altitude?"*

## Requirements

- [Little Navmap](https://albar965.github.io/littlenavmap.html) 3.0+ with the web server enabled (`Tools → Run Web Server`)
- Python 3.10+
- [Claude Desktop](https://claude.ai/download)

## Installation

**1. Clone or download this repository**

```bash
git clone https://github.com/bisnis3d/littlenavmap-mcp.git
```

Or just download `littlenavmap_mcp.py` directly.

**2. Install dependencies**

```bash
pip install "mcp[cli]" httpx
```

**3. Configure Claude Desktop**

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) and add the following entry inside `mcpServers`:

```json
{
  "mcpServers": {
    "littlenavmap": {
      "command": "python",
      "args": ["C:/path/to/littlenavmap_mcp.py"],
      "env": {
        "LNM_HOST": "127.0.0.1",
        "LNM_PORT": "8965",
        "LNM_DB_PATH": "C:/Users/YOUR_USERNAME/AppData/Roaming/ABarthel/little_navmap_db/little_navmap_msfs24.sqlite"
      }
    }
  }
}
```

Replace the path in `args` with the actual location of the script, and set `LNM_DB_PATH` to your LNM SQLite database. The default database path (if you omit `LNM_DB_PATH`) is `%APPDATA%\ABarthel\little_navmap_db\little_navmap_msfs24.sqlite`.

> **Note:** Use `127.0.0.1` instead of `localhost` — on some Windows systems `localhost` does not resolve correctly and causes connection errors.

**4. Restart Claude Desktop**

Right-click the tray icon → Quit, then reopen.

## Available Tools

| Tool | Source | Description |
|------|--------|-------------|
| `lnm_status` | WebAPI + SQLite | Health check — verifies both LNM web server and SQLite accessibility |
| `lnm_airport_info` | WebAPI | Full airport data: runways, COM frequencies, procedures, elevation |
| `lnm_airport_weather` | WebAPI | METAR/TAF from configured weather sources |
| `lnm_navaid_search` | SQLite | Search for a VOR or NDB by ident |
| `lnm_map_features` | SQLite | VORs, NDBs and airports within a lat/lon bounding box |
| `lnm_flightplan_get` | WebAPI | Active flight plan with waypoints, legs and procedures |
| `lnm_aircraft_info` | WebAPI | Real-time aircraft position, speed, altitude and fuel |
| `lnm_aircraft_progress` | WebAPI | Active leg, distance to destination, ETE and fuel state |
| `lnm_sim_info` | WebAPI | Simulator connection status |
| `lnm_ui_info` | WebAPI | Current map view (center position, zoom) |
| `lnm_map_image` | WebAPI | Returns the URL for a PNG map image of a given region |

Tools marked **WebAPI** require Little Navmap running with the web server active. Tools marked **SQLite** read directly from the LNM navigation database and work even when the simulator is not running.

Tools that require a connected simulator (`lnm_aircraft_info`, `lnm_aircraft_progress`) will return an error if MSFS is not running or not connected to Little Navmap.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LNM_HOST` | `127.0.0.1` | LNM web server host |
| `LNM_PORT` | `8965` | LNM web server port |
| `LNM_DB_PATH` | `%APPDATA%\ABarthel\little_navmap_db\little_navmap_msfs24.sqlite` | Path to the LNM SQLite navigation database |

## Notes

- `lnm_navaid_search` and `lnm_map_features` use SQLite direct access because `/api/navaid/info` and `/api/map/features` do not exist in LNM WebAPI 3.0.18. If a future version adds these endpoints, the tools can be migrated to WebAPI.
- The SQLite database is the same one LNM uses internally. It is read-only — this server never writes to it.
- Tested on LNM 3.0.18 with MSFS 2024 navigation data.

## License

MIT
