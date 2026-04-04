from .model_support import IMAGE_MODELS, PROFILE_MODELS

"""Tool schemas — what the LLM sees when deciding which weather tool to call."""

# =============================================================================
# Tier 1 — Data (Python, NWS API direct)
# =============================================================================

WX_CONDITIONS = {
    "name": "wx_conditions",
    "description": (
        "Current weather conditions for a location — latest observation with "
        "temperature, wind, visibility, sky cover, dewpoint, and pressure. "
        "Use this as the default for 'how's the weather' questions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude"},
            "lon": {"type": "number", "description": "Longitude"},
        },
        "required": ["lat", "lon"],
    },
}

WX_FORECAST = {
    "name": "wx_forecast",
    "description": (
        "NWS 7-day or hourly forecast for a US location. Returns detailed "
        "periods with temperature, wind, precipitation chance. "
        "Use for 'what's the forecast' or 'will it rain tomorrow' questions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude"},
            "lon": {"type": "number", "description": "Longitude"},
            "hourly": {
                "type": "boolean",
                "description": "If true, return hourly forecast instead of 7-day",
            },
        },
        "required": ["lat", "lon"],
    },
}

WX_ALERTS = {
    "name": "wx_alerts",
    "description": (
        "Active NWS weather alerts (warnings, watches, advisories) for a "
        "location or state. Use when someone asks about warnings or severe threats."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude (use with lon)"},
            "lon": {"type": "number", "description": "Longitude (use with lat)"},
            "state": {"type": "string", "description": "Two-letter state code (e.g., OK, TX). Alternative to lat/lon."},
        },
    },
}

WX_METAR = {
    "name": "wx_metar",
    "description": (
        "Raw and decoded METAR observation for an ICAO station. Returns "
        "temperature, dewpoint, wind, altimeter, visibility, clouds, and raw METAR string."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "station": {"type": "string", "description": "ICAO station code (e.g., KPDX, KOKC, KJFK)"},
        },
        "required": ["station"],
    },
}

WX_BRIEF = {
    "name": "wx_brief",
    "description": (
        "Quick weather briefing — conditions + 3-period forecast + alert count "
        "in one call. Use for fast overviews."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude"},
            "lon": {"type": "number", "description": "Longitude"},
        },
        "required": ["lat", "lon"],
    },
}

WX_GLOBAL = {
    "name": "wx_global",
    "description": (
        "Global weather via Open-Meteo — works ANYWHERE in the world, not just US. "
        "Returns temperature, humidity, wind, precipitation. "
        "Use for international locations where NWS data is unavailable."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude"},
            "lon": {"type": "number", "description": "Longitude"},
        },
        "required": ["lat", "lon"],
    },
}

WX_SEVERE = {
    "name": "wx_severe",
    "description": (
        "SPC severe weather outlook — Day 1 categorical risk level and active watches. "
        "Use when someone asks about severe weather risk or SPC forecasts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude"},
            "lon": {"type": "number", "description": "Longitude"},
            "state": {"type": "string", "description": "Two-letter state code. Alternative to lat/lon."},
        },
    },
}

# =============================================================================
# Tier 2 — Visualization
# =============================================================================

WX_MODEL_IMAGE = {
    "name": "wx_model_image",
    "description": (
        "Render a weather model field as a PNG image — HRRR (3km), GFS (global), "
        "NAM, RAP, and the verified multi-model image subset. Shows CAPE, temperature, reflectivity, "
        "dewpoint, wind, helicity, and more. Provide lat/lon to zoom into a region. "
        "Supports cycle selection (e.g., 18 for 18z) and forecast hours. "
        "HRRR runs hourly (0-48h), GFS every 6h (0-384h)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "var": {
                "type": "string",
                "description": (
                    "Variable(s) to plot. Comma-separated for multiple in one call. "
                    "Standard fields: cape, refl, temp, dewpoint, rh, helicity, uh, gust, "
                    "wind, precip, mslp, heights_500, jet, srh, mlcape, mucape, cin. "
                    "Composite indices: stp (Significant Tornado Parameter), "
                    "scp (Supercell Composite), ehi (Energy-Helicity Index). "
                    "Example: 'cape,stp,srh,uh' generates 4 images in one call. "
                    "ALWAYS use comma-separated when plotting multiple variables."
                ),
            },
            "model": {
                "type": "string",
                "enum": IMAGE_MODELS,
                "description": (
                    "Verified Rust-backed image model set (default: hrrr). Includes HRRR, HRRRAK, GFS, GDAS, GraphCast, RAP, NAM, GEFS, AI-GFS, NBM, and HiResW."
                ),
            },
            "lat": {"type": "number", "description": "Center latitude for regional zoom"},
            "lon": {"type": "number", "description": "Center longitude for regional zoom"},
            "radius_km": {"type": "number", "description": "Zoom radius in km (default: 500)"},
            "fhour": {"type": "integer", "description": "Forecast hour (default: 0)"},
            "cycle": {"type": "integer", "description": "Model init cycle hour 0-23 (e.g., 18 for 18z). Omit for latest."},
            "date": {"type": "string", "description": "Model run date YYYYMMDD. Defaults to today."},
        },
        "required": ["var"],
    },
}

WX_RADAR_IMAGE = {
    "name": "wx_radar_image",
    "description": (
        "Render NEXRAD radar as a PNG — high-resolution Level 2 data with "
        "bilinear interpolation through the current radar backend. Shows reflectivity, velocity, or dual-pol products. "
        "Default: 1024px, 200km range, 10dBZ noise filter. "
        "Specify a NEXRAD site (e.g., KTLX) or lat/lon to find nearest."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "site": {"type": "string", "description": "NEXRAD 4-letter site ID (e.g., KTLX, KRTX, KLOT)"},
            "lat": {"type": "number", "description": "Latitude (finds nearest radar)"},
            "lon": {"type": "number", "description": "Longitude (finds nearest radar)"},
            "product": {
                "type": "string",
                "enum": ["ref", "vel", "sw", "zdr", "rho", "phi", "srv", "vil"],
                "description": (
                    "Radar product (default: ref). "
                    "srv and vil are currently available only through the rustdar backend."
                ),
            },
            "size": {"type": "integer", "description": "Image size in pixels (default: 1024)"},
            "min_dbz": {"type": "number", "description": "Minimum dBZ threshold (default: 10). Use 0 for no filter."},
            "range_km": {"type": "number", "description": "Display range in km (default: 200)"},
        },
    },
}

WX_STORM_IMAGE = {
    "name": "wx_storm_image",
    "description": (
        "Render radar with storm analysis overlays — shows reflectivity with "
        "mesocyclone, TVS, hail, or storm-cell markers depending on the active "
        "radar backend, and returns structured analysis metadata alongside the PNG."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "site": {"type": "string", "description": "NEXRAD 4-letter site ID (e.g., KTLX)"},
            "lat": {"type": "number", "description": "Latitude (finds nearest radar)"},
            "lon": {"type": "number", "description": "Longitude (finds nearest radar)"},
            "size": {"type": "integer", "description": "Image size in pixels (default: 1024)"},
            "min_dbz": {"type": "number", "description": "Minimum dBZ threshold (default: 10). Use 0 for no filter."},
            "range_km": {"type": "number", "description": "Display range in km (default: 200)"},
        },
    },
}

# =============================================================================
# Tier 3 — Calculations
# =============================================================================

WX_CALC = {
    "name": "wx_calc",
    "description": (
        "Perform a verified meteorological calculation using metrust — "
        "205 Rust-backed functions verified against MetPy. "
        "Supports thermodynamics (dewpoint, LCL, CAPE, wet bulb), "
        "kinematics (shear, vorticity, helicity), "
        "fire weather (Fosberg, Haines, hot-dry-windy), and more. "
        "Pass the function name and arguments with units."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "function": {
                "type": "string",
                "description": (
                    "metrust.calc function name. Common: "
                    "dewpoint_from_relative_humidity, wind_speed, wind_direction, "
                    "wind_chill, heat_index, lcl, lfc, el, cape_cin, "
                    "potential_temperature, equivalent_potential_temperature, "
                    "wet_bulb_temperature, fosberg_fire_weather_index, "
                    "bulk_shear, storm_relative_helicity, lifted_index, "
                    "k_index, total_totals, precipitable_water"
                ),
            },
            "args": {
                "type": "object",
                "description": (
                    "Arguments as key-value pairs with units where applicable "
                    "(e.g., {'temperature': '30 degC', 'relative_humidity': '65 percent'})"
                ),
            },
        },
        "required": ["function"],
    },
}

WX_SOUNDING = {
    "name": "wx_sounding",
    "description": (
        "Get model-derived atmospheric sounding at a point — downloads HRRR "
        "pressure-level data and computes convective parameters."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude"},
            "lon": {"type": "number", "description": "Longitude"},
            "model": {
                "type": "string",
                "enum": PROFILE_MODELS,
                "description": "Profile-capable model source (default: hrrr)",
            },
        },
        "required": ["lat", "lon"],
    },
}


WX_ECAPE = {
    "name": "wx_ecape",
    "description": (
        "Compute ECAPE, NCAPE, CAPE, CIN, LFC, EL, storm motion, and optional "
        "parcel-path arrays from a model-derived sounding at a point. Uses the "
        "parity-verified ecape-rs runner."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude"},
            "lon": {"type": "number", "description": "Longitude"},
            "model": {
                "type": "string",
                "enum": PROFILE_MODELS,
                "description": "Profile-capable model source (default: hrrr)",
            },
            "cape_type": {
                "type": "string",
                "enum": ["surface_based", "most_unstable", "mixed_layer", "user_defined"],
                "description": "Parcel source for ECAPE calculations (default: most_unstable)",
            },
            "pseudoadiabatic": {
                "type": "boolean",
                "description": "If true, use pseudoadiabatic parcel behavior; if false, use irreversible behavior (default: true)",
            },
            "storm_motion_type": {
                "type": "string",
                "enum": ["right_moving", "left_moving", "mean_wind", "user_defined"],
                "description": "Storm-motion method: Bunkers right mover, Bunkers left mover, Bunkers mean wind, or user-defined (default: right_moving)",
            },
            "storm_motion_u_ms": {
                "type": "number",
                "description": "Custom storm-motion u component in m/s; use with storm_motion_v_ms",
            },
            "storm_motion_v_ms": {
                "type": "number",
                "description": "Custom storm-motion v component in m/s; use with storm_motion_u_ms",
            },
            "include_parcel_profile": {
                "type": "boolean",
                "description": "If true, include the full aligned ECAPE parcel path arrays",
            },
        },
        "required": ["lat", "lon"],
    },
}

ALL_SCHEMAS = [
    WX_CONDITIONS, WX_FORECAST, WX_ALERTS, WX_METAR, WX_BRIEF,
    WX_GLOBAL, WX_SEVERE,
    WX_MODEL_IMAGE, WX_RADAR_IMAGE, WX_STORM_IMAGE,
    WX_CALC, WX_SOUNDING, WX_ECAPE,
]


