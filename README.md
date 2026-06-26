# Little Navmap MCP Server

An MCP (Model Context Protocol) server that exposes the [Little Navmap](https://albar965.github.io/littlenavmap.html) WebAPI as tools for Claude Desktop and other MCP-compatible clients.

Ask Claude things like:
- *"What are the runways and frequencies at LEMD?"*
- *"Show me all VORs between lat 40-42, lon -5 to -3"*
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
      "args": ["C:/path/to/littlenavmap_mcp.py"]
    }
  }
}
```

Replace `C:/path/to/littlenavmap_mcp.py` with the actual path to the script.

**4. Restart Claude Desktop**

Right-click the tray icon → Quit, then reopen.

## Configuration

By default the server connects to `http://localhost:8965`. You can override this with environment variables:

```json
"env": {
  "LNM_HOST": "localhost",
  "LNM_PORT": "8965"
}
```

This is useful if Little Navmap is running on a different machine on your local network.

## Available Tools

| Tool | Description |
|------|-------------|
| `lnm_status` | Health check — verifies LNM web server is reachable |
| `lnm_airport_info` | Full airport data: runways, COM frequencies, procedures, elevation |
| `lnm_airport_weather` | METAR/TAF from configured weather sources |
| `lnm_map_features` | All navaids and airports within a lat/lon bounding box |
| `lnm_navaid_search` | Search for a VOR, NDB, waypoint or ILS by ident |
| `lnm_flightplan_get` | Active flight plan with waypoints, legs and procedures |
| `lnm_aircraft_info` | Real-time aircraft position, speed, altitude and fuel |
| `lnm_aircraft_progress` | Active leg, distance to destination, ETE and fuel state |
| `lnm_sim_info` | Simulator connection status |
| `lnm_ui_info` | Current map view (center position, zoom) |
| `lnm_map_image` | Returns the URL for a PNG map image of a given region |

Tools that require a connected simulator (`lnm_aircraft_info`, `lnm_aircraft_progress`) will return an error if MSFS is not running or not connected to Little Navmap.

## Notes

- The `aircraft`, `sim`, `flightplan` and `navaid` JSON endpoints exist in LNM 3.0 but are not part of the official public YAML spec. They work in practice but may change in future versions.
- The server uses `stdio` transport, which is the standard for local MCP servers used with Claude Desktop.

## License

MIT
