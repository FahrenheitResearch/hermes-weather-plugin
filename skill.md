---
name: weather-plugin
description: Guide for using the weather plugin — data queries, radar imagery, model maps, and meteorological calculations
version: 2.0.0
metadata:
  hermes:
    tags: [weather, radar, forecast, meteorology]
    category: weather
---

# Weather Plugin Usage Guide

You have 12 weather tools. Prefer lightweight data tools and only use images when asked.

## Tool Selection

**"How's the weather in [place]?"** → `wx_conditions`
**"What's the forecast?"** → `wx_forecast`
**"Any warnings/watches?"** → `wx_alerts`
**"Show me the radar"** → `wx_radar_image`
**"Show me CAPE/temperature/wind map"** → `wx_model_image` (use comma-separated vars: `"cape,helicity,uh,srh"` for multiple in ONE call)
**"What's the severe weather outlook?"** → `wx_severe`
**"Weather in Tokyo/London/etc"** → `wx_global` (worldwide)
**"Calculate dewpoint/wind chill/LCL"** → `wx_calc`
**"Is there a tornado threat?"** → `wx_severe` first, then `wx_model_image --var cape` or `--var helicity` for visual
**"What does the HRRR show?"** → `wx_model_image` with appropriate var
**"Show me the 18z HRRR"** → `wx_model_image` with `cycle: 18`
**"Sounding at a point"** → `wx_sounding`

## IMPORTANT: Only these 12 tools exist

`wx_conditions`, `wx_forecast`, `wx_alerts`, `wx_metar`, `wx_brief`, `wx_global`, `wx_severe`, `wx_radar_image`, `wx_model_image`, `wx_storm_image`, `wx_calc`, `wx_sounding`

Do NOT try to call any other tool names.

## Rules

1. **Start lightweight.** Use `wx_conditions` or `wx_brief` before heavier tools.
2. **Images only when asked.** Don't call image tools unless the user wants to SEE something.
3. **US vs international.** Use `wx_global` for non-US locations.
4. **Calculations are verified.** `wx_calc` uses metrust — 205 Rust-backed functions verified against MetPy.
5. **Don't stack redundant calls.** `wx_brief` already includes conditions + forecast + alerts.
6. **BATCH model images.** NEVER call wx_model_image multiple times for different variables. Use comma-separated vars in ONE call: `"cape,helicity,uh,srh"`. This generates all images at once.
7. **Severe weather package.** For severe weather analysis, use: `var: "cape,helicity,uh,srh"` — one call, 4 images.
8. **ZOOM to threat area.** When the user asks about a specific region (e.g., "Indiana to New York"), ALWAYS pass lat/lon and radius_km to zoom in. Don't show full CONUS when they asked about a corridor. Examples:
   - "Ohio Valley" → `lat: 39.5, lon: -83, radius_km: 400`
   - "Indiana to New York" → `lat: 40.5, lon: -77, radius_km: 500`
   - "Texas" → `lat: 31.5, lon: -99, radius_km: 500`
   - "Southeast" → `lat: 33, lon: -85, radius_km: 600`
   - "Great Plains" → `lat: 38, lon: -99, radius_km: 600`
   Use your geographic knowledge to pick appropriate center + radius.

## wx_calc Examples

- Dewpoint: `{"function": "dewpoint_from_relative_humidity", "args": {"temperature": "30 degC", "relative_humidity": "65 percent"}}`
- Wind chill: `{"function": "wind_chill", "args": {"temperature": "-5 degC", "speed": "30 km/hr"}}`
- Heat index: `{"function": "heat_index", "args": {"temperature": "95 degF", "relative_humidity": "60 percent"}}`
- LCL: `{"function": "lcl", "args": {"pressure": "1000 hPa", "temperature": "30 degC", "dewpoint": "20 degC"}}`

## Image Tools

`wx_radar_image` and `wx_model_image` return PNG file paths in JSON.

For radar: provide NEXRAD site ID (KRTX=Portland, KTLX=OKC, KLOT=Chicago) or lat/lon. Default 1024px, 200km range, 10dBZ noise filter.

For model images: specify variable (cape, refl, temp, dewpoint, rh, gust, helicity, uh, precip, mslp, heights_500, jet, srh). Add lat/lon + radius_km to zoom. Use cycle parameter for specific model runs.
