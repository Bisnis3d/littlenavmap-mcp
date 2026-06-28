"""
Little Navmap MCP Server
========================
Expone la WebAPI REST de Little Navmap (http://127.0.0.1:8965) como tools MCP.
Requiere que Little Navmap esté corriendo con el web server activo
(Tools → Run Web Server).

Endpoints cubiertos (LNM WebAPI v3.0):
  - /api/airport/info          → lnm_airport_info
  - /api/airport/weather       → lnm_airport_weather
  - /api/aircraft/info         → lnm_aircraft_info (sim conectado)
  - /api/aircraft/progress     → lnm_aircraft_progress (sim conectado)
  - /api/sim/info              → lnm_sim_info
  - /api/flightplan            → lnm_flightplan_get
  - /api/ui/info               → lnm_ui_info
  - /api/map/image             → lnm_map_image

Endpoints via SQLite directo (no existen en WebAPI v3.0.18):
  - lnm_navaid_search          → tablas vor, ndb del SQLite de LNM
  - lnm_map_features           → tablas vor, ndb, airport del SQLite de LNM

Uso (stdio, para Claude Desktop):
  python littlenavmap_mcp.py

Configuración claude_desktop_config.json:
  {
    "mcpServers": {
      "littlenavmap": {
        "command": "python",
        "args": ["C:/ruta/a/littlenavmap_mcp.py"],
        "env": {
          "LNM_HOST": "127.0.0.1",
          "LNM_PORT": "8965",
          "LNM_DB_PATH": "C:/Users/TU_USUARIO/AppData/Roaming/ABarthel/little_navmap_db/little_navmap_msfs24.sqlite"
        }
      }
    }
  }
"""

import json
import os
import sqlite3
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ─── Configuración ────────────────────────────────────────────────────────────

LNM_HOST = os.getenv("LNM_HOST", "127.0.0.1")
LNM_PORT = os.getenv("LNM_PORT", "8965")
BASE_URL = f"http://{LNM_HOST}:{LNM_PORT}"
TIMEOUT = 10.0

# Ruta al SQLite de LNM — configurable via variable de entorno
_DEFAULT_DB = os.path.join(
    os.environ.get("APPDATA", ""),
    "ABarthel", "little_navmap_db", "little_navmap_msfs24.sqlite"
)
LNM_DB_PATH = os.getenv("LNM_DB_PATH", _DEFAULT_DB)

mcp = FastMCP("littlenavmap_mcp")


# ─── Cliente HTTP ─────────────────────────────────────────────────────────────

async def _get(path: str, params: Optional[dict] = None) -> dict:
    """Realiza GET a la WebAPI de LNM y devuelve JSON o lanza ValueError."""
    url = f"{BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        raise ValueError(
            f"No se puede conectar a Little Navmap en {BASE_URL}. "
            "Verifica que LNM esté corriendo y el web server activo "
            "(Tools → Run Web Server)."
        )
    except httpx.HTTPStatusError as e:
        raise ValueError(
            f"LNM devolvió error HTTP {e.response.status_code} para {path}. "
            f"Respuesta: {e.response.text[:200]}"
        )
    except httpx.TimeoutException:
        raise ValueError(f"Timeout al contactar LNM en {url}.")


# ─── Cliente SQLite ───────────────────────────────────────────────────────────

def _db_query(sql: str, params: tuple = ()) -> list[dict]:
    """Ejecuta una query en el SQLite de LNM y devuelve lista de dicts."""
    if not os.path.isfile(LNM_DB_PATH):
        raise ValueError(
            f"Base de datos de LNM no encontrada en '{LNM_DB_PATH}'. "
            "Configura LNM_DB_PATH con la ruta correcta al archivo .sqlite."
        )
    conn = sqlite3.connect(LNM_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)

def _err(e: Exception) -> str:
    return f"Error: {e}"


# ─── Modelos de entrada ───────────────────────────────────────────────────────

class AirportIdent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    ident: str = Field(
        ...,
        description="ICAO identifier del aeropuerto (e.g. 'LEMD', 'LPPT', 'EGLL'). "
                    "No se soportan IATA ni identificadores locales.",
        min_length=2,
        max_length=6,
    )


class MapFeaturesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    toplat: float = Field(..., description="Latitud norte del rectángulo (e.g. 41.0)", ge=-90, le=90)
    bottomlat: float = Field(..., description="Latitud sur del rectángulo (e.g. 40.0)", ge=-90, le=90)
    leftlon: float = Field(..., description="Longitud oeste del rectángulo (e.g. -4.0)", ge=-180, le=180)
    rightlon: float = Field(..., description="Longitud este del rectángulo (e.g. -3.0)", ge=-180, le=180)


class MapImageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: int = Field(default=800, description="Ancho de la imagen en píxeles", ge=100, le=4096)
    height: int = Field(default=600, description="Alto de la imagen en píxeles", ge=100, le=4096)
    leftlon: Optional[float] = Field(default=None, description="Límite oeste (longitud)", ge=-180, le=180)
    rightlon: Optional[float] = Field(default=None, description="Límite este (longitud)", ge=-180, le=180)
    toplat: Optional[float] = Field(default=None, description="Límite norte (latitud)", ge=-90, le=90)
    bottomlat: Optional[float] = Field(default=None, description="Límite sur (latitud)", ge=-90, le=90)
    detailfactor: Optional[float] = Field(
        default=None,
        description="Factor de detalle del mapa (1.0 = normal, >1 más detalle)",
        ge=0.1,
        le=10.0,
    )


# ─── Tools — WebAPI ───────────────────────────────────────────────────────────

@mcp.tool(
    name="lnm_airport_info",
    annotations={"title": "Información de aeropuerto", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def lnm_airport_info(params: AirportIdent) -> str:
    """Obtiene información completa de un aeropuerto desde la base de datos de LNM.

    Devuelve datos como nombre, elevación, coordenadas, pistas (número, longitud,
    superficie, heading), frecuencias COM/NAV, procedimientos disponibles y estado
    de la torre. Útil para planificación de vuelos GA y consulta pre-vuelo.

    Args:
        params (AirportIdent): Contiene:
            - ident (str): Código ICAO del aeropuerto (2-6 caracteres)

    Returns:
        str: JSON con los datos del aeropuerto incluyendo runways, frequencies,
             procedures, elevation (ft), coordinates y más.
    """
    try:
        data = await _get("/api/airport/info", {"ident": params.ident.upper()})
        return _fmt(data)
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="lnm_airport_weather",
    annotations={"title": "Meteorología de aeropuerto", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def lnm_airport_weather(params: AirportIdent) -> str:
    """Obtiene la meteorología actual de un aeropuerto desde LNM.

    Devuelve METAR, TAF y otros datos meteorológicos disponibles para el
    aeropuerto especificado. La disponibilidad depende de las fuentes de
    weather configuradas en LNM (MSFS, NOAA, ActiveSky, etc.).

    Args:
        params (AirportIdent): Contiene:
            - ident (str): Código ICAO del aeropuerto

    Returns:
        str: JSON con datos meteorológicos (METAR, TAF, wind, visibility, ceiling).
    """
    try:
        data = await _get("/api/airport/weather", {"ident": params.ident.upper()})
        return _fmt(data)
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="lnm_aircraft_info",
    annotations={"title": "Estado del aircraft del simulador", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def lnm_aircraft_info() -> str:
    """Obtiene el estado actual del aircraft del simulador en tiempo real.

    Requiere que MSFS esté corriendo y conectado a Little Navmap. Devuelve
    posición (lat/lon), altitud (ft MSL y AGL), velocidades (IAS, GS, TAS),
    heading, vertical speed, fuel, engine state y más.

    Returns:
        str: JSON con todos los parámetros de vuelo en tiempo real.
             Devuelve error si el simulador no está conectado.
    """
    try:
        data = await _get("/api/aircraft/info")
        return _fmt(data)
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="lnm_aircraft_progress",
    annotations={"title": "Progreso de vuelo en tiempo real", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def lnm_aircraft_progress() -> str:
    """Obtiene datos de progreso de vuelo del aircraft activo en el simulador.

    Incluye información sobre el leg activo, próximo waypoint, distancia y
    tiempo estimado a destino, bearing, altitud requerida, fuel restante y
    estado de climb/descent. Equivale a la pestaña Progress de LNM.

    Requiere simulador conectado y flight plan cargado en LNM.

    Returns:
        str: JSON con datos de progreso: waypoint activo, bearing to next,
             distance remaining, ETE, fuel state y altitude requirements.
    """
    try:
        data = await _get("/api/aircraft/progress")
        return _fmt(data)
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="lnm_sim_info",
    annotations={"title": "Información del simulador", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def lnm_sim_info() -> str:
    """Obtiene el estado de la conexión con el simulador y datos generales de la sesión.

    Devuelve información sobre qué simulador está conectado, versión, estado
    de la conexión (conectado/pausado/etc.) y datos de sesión como tiempo de vuelo.

    Returns:
        str: JSON con tipo de simulador, estado de conexión y metadatos de sesión.
    """
    try:
        data = await _get("/api/sim/info")
        return _fmt(data)
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="lnm_flightplan_get",
    annotations={"title": "Flight plan activo en LNM", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def lnm_flightplan_get() -> str:
    """Obtiene el flight plan actualmente cargado en Little Navmap.

    Devuelve la lista completa de waypoints con coordenadas, tipo (airport,
    VOR, NDB, waypoint, etc.), distancia y curso de cada leg, altitud de
    crucero, aeropuerto de salida y destino, y procedimientos activos
    (SID, STAR, approach).

    Returns:
        str: JSON con el flight plan completo. Si no hay plan cargado,
             devuelve un plan vacío.
    """
    try:
        data = await _get("/api/flightplan")
        return _fmt(data)
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="lnm_ui_info",
    annotations={"title": "Estado de la UI de LNM", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def lnm_ui_info() -> str:
    """Obtiene información sobre el estado actual de la interfaz de LNM.

    Devuelve la posición del mapa visible (centro, zoom), distancia de
    visualización y otros parámetros de la UI.

    Returns:
        str: JSON con la posición central del mapa, zoom y metadatos de la vista.
    """
    try:
        data = await _get("/api/ui/info")
        return _fmt(data)
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="lnm_map_image",
    annotations={"title": "Imagen del mapa de LNM", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def lnm_map_image(params: MapImageInput) -> str:
    """Obtiene la URL de la imagen del mapa actual de LNM para una región.

    Devuelve la URL construida para solicitar una imagen PNG del mapa de LNM.
    La imagen refleja todos los ajustes de visualización actuales del mapa
    (aeropuertos, navaids, flight plan, etc.).

    Nota: Este tool devuelve la URL, no la imagen en sí. Para obtener la imagen
    debes hacer un GET a esa URL mientras LNM esté corriendo.

    Args:
        params (MapImageInput): Dimensiones y región opcional:
            - width (int): Ancho en píxeles (default 800)
            - height (int): Alto en píxeles (default 600)
            - leftlon/rightlon/toplat/bottomlat: Límites geográficos opcionales
            - detailfactor (float): Factor de detalle (default 1.0)

    Returns:
        str: JSON con la URL completa de la imagen y los parámetros usados.
    """
    query: dict = {"width": params.width, "height": params.height}
    if params.leftlon is not None:
        query["leftlon"] = params.leftlon
    if params.rightlon is not None:
        query["rightlon"] = params.rightlon
    if params.toplat is not None:
        query["toplat"] = params.toplat
    if params.bottomlat is not None:
        query["bottomlat"] = params.bottomlat
    if params.detailfactor is not None:
        query["detailfactor"] = params.detailfactor

    param_str = "&".join(f"{k}={v}" for k, v in query.items())
    url = f"{BASE_URL}/api/map/image?{param_str}"
    return _fmt({"map_image_url": url, "params": query, "base_url": BASE_URL})


# ─── Tools — SQLite directo ───────────────────────────────────────────────────

@mcp.tool(
    name="lnm_navaid_search",
    annotations={"title": "Buscar navaid por ident", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def lnm_navaid_search(
    ident: str = Field(..., description="Identificador del navaid (e.g. 'BCN', 'TAU', 'AMTEL')", min_length=2, max_length=10),
) -> str:
    """Busca VORs y NDBs por identificador en la base de datos de LNM (SQLite directo).

    Devuelve tipo, frecuencia, coordenadas, región, rango y nombre del navaid.
    Busca simultáneamente en las tablas vor y ndb del SQLite de LNM.

    Nota: Este endpoint no existe en la WebAPI de LNM 3.0.18 — se accede
    directamente al SQLite en LNM_DB_PATH.

    Args:
        ident (str): Identificador del navaid (2-10 caracteres, case insensitive)

    Returns:
        str: JSON con listas 'vors' y 'ndbs' con los resultados encontrados.
    """
    try:
        ident_upper = ident.upper()

        vors = _db_query(
            """
            SELECT ident, name, frequency, range, mag_var,
                   lonx AS lon, laty AS lat, region, type
            FROM vor
            WHERE ident = ?
            ORDER BY name
            """,
            (ident_upper,)
        )

        ndbs = _db_query(
            """
            SELECT ident, name, frequency, range,
                   lonx AS lon, laty AS lat, region, type
            FROM ndb
            WHERE ident = ?
            ORDER BY name
            """,
            (ident_upper,)
        )

        return _fmt({
            "ident": ident_upper,
            "vors": vors,
            "ndbs": ndbs,
            "total": len(vors) + len(ndbs),
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="lnm_map_features",
    annotations={"title": "Navaids y aeropuertos en una región", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def lnm_map_features(params: MapFeaturesInput) -> str:
    """Obtiene VORs, NDBs y aeropuertos dentro de un rectángulo geográfico.

    Consulta directamente el SQLite de LNM (las tablas vor, ndb y airport).
    Útil para planificación de rutas VOR-to-VOR o identificar navaids en
    una región de interés.

    Nota: Este endpoint no existe en la WebAPI de LNM 3.0.18 — se accede
    directamente al SQLite en LNM_DB_PATH.

    Args:
        params (MapFeaturesInput): Rectángulo definido por:
            - toplat (float): Latitud norte
            - bottomlat (float): Latitud sur
            - leftlon (float): Longitud oeste
            - rightlon (float): Longitud este

    Returns:
        str: JSON con arrays 'vors', 'ndbs' y 'airports' dentro del rectángulo.
    """
    try:
        lat_min = min(params.toplat, params.bottomlat)
        lat_max = max(params.toplat, params.bottomlat)
        lon_min = min(params.leftlon, params.rightlon)
        lon_max = max(params.leftlon, params.rightlon)

        bounds = (lat_min, lat_max, lon_min, lon_max)

        vors = _db_query(
            """
            SELECT ident, name, frequency, range, mag_var,
                   lonx AS lon, laty AS lat, region, type
            FROM vor
            WHERE laty BETWEEN ? AND ?
              AND lonx BETWEEN ? AND ?
            ORDER BY ident
            """,
            bounds
        )

        ndbs = _db_query(
            """
            SELECT ident, name, frequency, range,
                   lonx AS lon, laty AS lat, region, type
            FROM ndb
            WHERE laty BETWEEN ? AND ?
              AND lonx BETWEEN ? AND ?
            ORDER BY ident
            """,
            bounds
        )

        airports = _db_query(
            """
            SELECT ident, name, elevation,
                   lonx AS lon, laty AS lat, country, state,
                   num_runway_hard, num_runway_soft, longest_runway_length
            FROM airport
            WHERE laty BETWEEN ? AND ?
              AND lonx BETWEEN ? AND ?
            ORDER BY ident
            """,
            bounds
        )

        return _fmt({
            "bbox": {"lat_min": lat_min, "lat_max": lat_max,
                     "lon_min": lon_min, "lon_max": lon_max},
            "vors": vors,
            "ndbs": ndbs,
            "airports": airports,
            "totals": {"vors": len(vors), "ndbs": len(ndbs), "airports": len(airports)},
        })
    except Exception as e:
        return _err(e)


# ─── Tool — Status (WebAPI + SQLite) ─────────────────────────────────────────

@mcp.tool(
    name="lnm_status",
    annotations={"title": "Estado general de LNM", "readOnlyHint": True,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
async def lnm_status() -> str:
    """Verifica el estado de Little Navmap: conectividad WebAPI y accesibilidad del SQLite.

    Comprueba dos cosas independientemente:
    - WebAPI: hace ping al web server de LNM en BASE_URL
    - SQLite: verifica que el archivo .sqlite existe y es accesible

    Returns:
        str: JSON con estado de webapi y sqlite, rutas usadas y mensajes descriptivos.
    """
    result = {
        "webapi": {"status": "error", "base_url": BASE_URL, "message": ""},
        "sqlite": {"status": "error", "path": LNM_DB_PATH, "message": ""},
    }

    # Check WebAPI
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BASE_URL}/")
            if response.status_code < 400:
                result["webapi"]["status"] = "ok"
                result["webapi"]["message"] = "LNM web server alcanzable."
            else:
                result["webapi"]["message"] = f"HTTP {response.status_code}."
    except httpx.ConnectError:
        result["webapi"]["message"] = (
            "LNM no responde. Verifica que esté abierto y el web server activo "
            "(Tools → Run Web Server)."
        )
    except Exception as e:
        result["webapi"]["message"] = str(e)

    # Check SQLite
    try:
        rows = _db_query("SELECT COUNT(*) AS n FROM vor")
        result["sqlite"]["status"] = "ok"
        result["sqlite"]["message"] = f"SQLite accesible. {rows[0]['n']} VORs en base de datos."
    except Exception as e:
        result["sqlite"]["message"] = str(e)

    overall = "ok" if all(v["status"] == "ok" for v in result.values()) else "partial" \
              if any(v["status"] == "ok" for v in result.values()) else "error"
    result["overall"] = overall

    return _fmt(result)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
