"""NWS and weather API client — pure Python, no binary dependencies.

Handles all data fetching for Tier 1 tools:
- NWS API (api.weather.gov) for US conditions, forecasts, alerts
- aviationweather.gov for METAR observations
- SPC (spc.noaa.gov) for severe weather outlooks
- Open-Meteo for global weather (non-US)
"""

import json
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "(hermes-weather-plugin, github.com/FahrenheitResearch)",
    "Accept": "application/geo+json,application/json",
})
_TIMEOUT = 30


def _get(url: str, params: dict = None) -> dict:
    """GET with timeout and error handling."""
    resp = _SESSION.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _get_text(url: str, params: dict = None) -> str:
    resp = _SESSION.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# NWS API (api.weather.gov)
# ---------------------------------------------------------------------------

def _resolve_gridpoint(lat: float, lon: float) -> dict:
    """Resolve lat/lon to NWS gridpoint metadata."""
    data = _get(f"https://api.weather.gov/points/{lat},{lon}")
    return data["properties"]


def get_conditions(lat: float, lon: float) -> str:
    """Current conditions: latest observation + station info."""
    try:
        point = _resolve_gridpoint(lat, lon)
        stations_url = point["observationStations"]
        stations = _get(stations_url)
        if not stations.get("features"):
            return json.dumps({"error": "No observation stations found"})

        station = stations["features"][0]
        station_id = station["properties"]["stationIdentifier"]
        obs_url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
        obs = _get(obs_url)
        props = obs["properties"]

        return json.dumps({
            "station": station_id,
            "station_name": station["properties"].get("name", ""),
            "timestamp": props.get("timestamp"),
            "temperature_c": _val(props, "temperature"),
            "dewpoint_c": _val(props, "dewpoint"),
            "wind_speed_kmh": _val(props, "windSpeed"),
            "wind_direction_deg": _val(props, "windDirection"),
            "wind_gust_kmh": _val(props, "windGust"),
            "barometric_pressure_pa": _val(props, "barometricPressure"),
            "visibility_m": _val(props, "visibility"),
            "text_description": props.get("textDescription", ""),
            "raw_metar": props.get("rawMessage", ""),
        })
    except Exception as e:
        return json.dumps({"error": f"conditions failed: {e}"})


def get_forecast(lat: float, lon: float, hourly: bool = False) -> str:
    """NWS 7-day or hourly forecast."""
    try:
        point = _resolve_gridpoint(lat, lon)
        url = point["forecastHourly"] if hourly else point["forecast"]
        data = _get(url)
        periods = data["properties"]["periods"]
        result = []
        for p in periods[:24 if hourly else 14]:
            result.append({
                "name": p.get("name", ""),
                "start": p.get("startTime"),
                "end": p.get("endTime"),
                "temperature": p.get("temperature"),
                "temperature_unit": p.get("temperatureUnit"),
                "wind_speed": p.get("windSpeed"),
                "wind_direction": p.get("windDirection"),
                "short_forecast": p.get("shortForecast"),
                "detailed_forecast": p.get("detailedForecast", ""),
                "precip_chance": p.get("probabilityOfPrecipitation", {}).get("value"),
            })
        return json.dumps({"periods": result, "location": {"lat": lat, "lon": lon}})
    except Exception as e:
        return json.dumps({"error": f"forecast failed: {e}"})


def get_alerts(lat: Optional[float] = None, lon: Optional[float] = None,
               state: Optional[str] = None) -> str:
    """Active NWS alerts by point or state."""
    try:
        params = {"status": "actual", "message_type": "alert"}
        if state:
            params["area"] = state.upper()
        elif lat is not None and lon is not None:
            params["point"] = f"{lat},{lon}"
        else:
            return json.dumps({"error": "Provide lat/lon or state"})

        data = _get("https://api.weather.gov/alerts/active", params=params)
        alerts = []
        for f in data.get("features", []):
            p = f["properties"]
            alerts.append({
                "event": p.get("event"),
                "severity": p.get("severity"),
                "urgency": p.get("urgency"),
                "certainty": p.get("certainty"),
                "headline": p.get("headline"),
                "description": p.get("description", "")[:500],
                "onset": p.get("onset"),
                "expires": p.get("expires"),
                "sender_name": p.get("senderName"),
                "area_desc": p.get("areaDesc"),
            })
        return json.dumps({"count": len(alerts), "alerts": alerts})
    except Exception as e:
        return json.dumps({"error": f"alerts failed: {e}"})


# ---------------------------------------------------------------------------
# METAR (aviationweather.gov)
# ---------------------------------------------------------------------------

def get_metar(station: str) -> str:
    """Current METAR from aviationweather.gov."""
    try:
        url = "https://aviationweather.gov/api/data/metar"
        params = {"ids": station.upper(), "format": "json"}
        data = _get(url, params=params)
        if not data:
            return json.dumps({"error": f"No METAR for {station}"})
        obs = data[0] if isinstance(data, list) else data
        return json.dumps({
            "station": station.upper(),
            "raw": obs.get("rawOb", ""),
            "temperature_c": obs.get("temp"),
            "dewpoint_c": obs.get("dewp"),
            "wind_dir_deg": obs.get("wdir"),
            "wind_speed_kt": obs.get("wspd"),
            "wind_gust_kt": obs.get("wgst"),
            "visibility_mi": obs.get("visib"),
            "altimeter_inhg": obs.get("altim"),
            "flight_category": obs.get("fltcat"),
            "clouds": obs.get("clouds", []),
            "observation_time": obs.get("reportTime"),
        })
    except Exception as e:
        return json.dumps({"error": f"metar failed: {e}"})


# ---------------------------------------------------------------------------
# SPC Severe Weather
# ---------------------------------------------------------------------------

def get_severe(lat: Optional[float] = None, lon: Optional[float] = None,
               state: Optional[str] = None) -> str:
    """SPC categorical outlook + any active watches."""
    try:
        # Day 1 categorical outlook GeoJSON
        outlook_url = "https://www.spc.noaa.gov/products/outlook/day1otlk_cat.nolyr.geojson"
        outlook = _get(outlook_url)

        categories = []
        for f in outlook.get("features", []):
            props = f.get("properties", {})
            categories.append({
                "label": props.get("LABEL", ""),
                "label2": props.get("LABEL2", ""),
                "stroke": props.get("stroke", ""),
            })

        # Active watches
        watches_url = "https://www.spc.noaa.gov/products/watch/activeWW.json"
        try:
            watches_data = _get(watches_url)
            watches = watches_data if isinstance(watches_data, list) else []
        except Exception:
            watches = []

        return json.dumps({
            "day1_outlook": categories,
            "active_watches": watches,
        })
    except Exception as e:
        return json.dumps({"error": f"severe failed: {e}"})


# ---------------------------------------------------------------------------
# Open-Meteo (global, non-US)
# ---------------------------------------------------------------------------

def get_global(lat: float, lon: float) -> str:
    """Global weather via Open-Meteo — works everywhere."""
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "precipitation,weather_code,wind_speed_10m,wind_direction_10m,"
                       "wind_gusts_10m,surface_pressure",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
        }
        data = _get("https://api.open-meteo.com/v1/forecast", params=params)
        return json.dumps(data.get("current", {}))
    except Exception as e:
        return json.dumps({"error": f"global weather failed: {e}"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _val(props: dict, key: str):
    """Extract value from NWS observation property (handles nested {value, unitCode})."""
    v = props.get(key)
    if isinstance(v, dict):
        return v.get("value")
    return v
