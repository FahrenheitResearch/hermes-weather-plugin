# Hermes Weather Plugin

Weather plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent). 13 tools covering current conditions, forecasts, alerts, model imagery, radar, and meteorological calculations across an expanded backend model set.

Data tools call NWS/SPC/METAR APIs directly in Python. All image rendering happens in Rust -- no matplotlib in the rendering path.

## Tools

### Data (Python)
| Tool | What it returns |
|------|-----------------|
| `wx_conditions` | Current obs: temperature, wind, sky, dewpoint |
| `wx_forecast` | NWS 7-day or hourly forecast |
| `wx_alerts` | Active warnings, watches, advisories |
| `wx_metar` | Raw/decoded METAR for any ICAO station |
| `wx_brief` | Conditions + forecast + alert count in one call |
| `wx_global` | Non-US locations via Open-Meteo |
| `wx_severe` | SPC Day 1 categorical outlook + active watches |

### Images (Rust)
| Tool | What it returns |
|------|-----------------|
| `wx_model_image` | NWP field rendered as PNG -- 22+ products, 11 verified models, batch support |
| `wx_radar_image` | NEXRAD Level 2 radar image through the current radar backend (default rustdar) |
| `wx_storm_image` | Reflectivity image with storm-analysis overlays plus detection metadata |

### Calculations (Rust via PyO3)
| Tool | What it returns |
|------|-----------------|
| `wx_calc` | Any of 205 meteorological functions (dewpoint, CAPE, LCL, wind chill, etc.) |
| `wx_sounding` | Model sounding at a point -- 40 pressure levels + all derived parameters |
| `wx_ecape` | ECAPE, NCAPE, CAPE, CIN, LFC, EL, storm motion, and optional parcel path from a model sounding |

## Model Images

22+ fields rendered with color tables from Solarpower07. Lambert Conformal projection, state/country borders, colorbars.

**Instability**: CAPE (surface, mixed-layer, most-unstable, 0-3km), CIN
**Shear/Helicity**: SRH 0-1km, SRH 0-3km, updraft helicity, 0-6km bulk shear, 0-1km bulk shear
**Surface**: Temperature, dewpoint, RH, wind gust, cloud cover, precipitation, visibility
**Composites**: STP, SCP, EHI
**Reflectivity**: Composite reflectivity (27-color discrete palette)

Comma-separated batch: `"cape,srh,uh,stp"` renders 4 images in one tool call.

Average render time: 177ms per image.

## Model Support

- `wx_model_image`: verified surface/image subset
  - `aigfs`, `gdas`, `gefs`, `gfs`, `graphcast`, `hiresw`, `hrrr`, `hrrrak`, `nam`, `nbm`, `rap`
- `wx_sounding`: verified profile subset
  - `gdas`, `gfs`, `graphcast`, `hrrr`, `hrrrak`, `rrfs`
- `wx_ecape`: uses the same verified profile subset as `wx_sounding`

Models outside those sets may exist in the backend stack, but they are not exposed in Hermes until the extraction path is verified against the actual tool behavior.

## Sounding Parameters

`wx_sounding` downloads model pressure-level data from the verified profile subset and computes:

- **CAPE/CIN**: Surface-based, mixed-layer, most-unstable
- **Levels**: LCL (pressure, temperature, height AGL), LFC, EL
- **Indices**: Lifted Index, K-Index, Total Totals
- **Shear**: 0-1km and 0-6km bulk shear, SRH 0-1km and 0-3km
- **Storm motion**: Bunkers right-mover
- **Composites**: STP (fixed-layer)
- **Moisture**: Precipitable water, freezing level
- **Lapse rates**: 0-3km, 700-500mb
- **Profile**: Standard levels (1000, 925, 850, 700, 500, 300, 250 mb) with T, Td, wind

## ECAPE

`wx_ecape` downloads the same model sounding profile and runs the parity-verified `ecape-rs` runner.

- Defaults: `cape_type=most_unstable`, `storm_motion_type=right_moving`, `pseudoadiabatic=true`
- Returns: `ECAPE`, `NCAPE`, `CAPE`, `CIN`, `LFC`, `EL`, storm-motion `u/v`
- Optional: `include_parcel_profile=true` to return the full aligned parcel path arrays
- Supported storm motion modes:
- `right_moving` = Bunkers right mover
- `left_moving` = Bunkers left mover
- `mean_wind` = Bunkers mean wind
- `user_defined` = explicit `storm_motion_u_ms` / `storm_motion_v_ms`

## Stack

```
Plugin (Python)
  â”œâ”€â”€ Data: requests â†’ NWS / SPC / METAR / Open-Meteo APIs
  â”œâ”€â”€ Model images: rusbie â†’ cfrust â†’ wrf-render
  â”‚                  (download)  (decode)  (rasterize)
  â”œâ”€â”€ Radar: radar-render binary (rustdar)
  â””â”€â”€ Calculations: metrust-py (205 functions, PyO3 â†’ Rust)
```

No eccodes, no Fortran, no C libraries in the Rust components. The only system dependency is a working Python environment.

## Python Packages

```
metrust      â€” 205 meteorological calculations (PyO3 â†’ Rust)
cfrust       â€” GRIB2 decoder (pure Rust, replaces cfgrib/eccodes)
rusbie       â€” NWP downloader with byte-range .idx filtering
rustweather  â€” Plotting wrapper
rustplots    â€” MetPy-compatible plotting
wrf-rust     â€” Solarpower07 color tables + rasterizer
```

## Rust Binary

```
radar-render â€” NEXRAD Level 2 download + parse + render (from rustdar)
```

## Setup

```bash
# Install Python packages
pip install metrust cfrust rusbie rustweather

# Install from source (not yet on PyPI)
pip install -e /path/to/rustplots
pip install -e /path/to/wrf-rust

# Build radar binary
cd /path/to/rustdar
cargo build --release --bin radar-render

# Build ECAPE runner
cd /path/to/ecape-rs
cargo build --release --bin run_case

# Copy plugin to Hermes
cp -r weather ~/.hermes/plugins/

## Radar

Hermes keeps a stable radar tool contract and routes it through the configured radar backend. The default backend is `rustdar` via the `radar-render` CLI.

Supported radar products:
- `ref`, `vel`, `sw`, `zdr`, `rho`, `phi`: available through both radar backends
- `srv`, `vil`: currently available through the `rustdar` backend only

# (Optional) Select radar backend and binary path
export RADAR_BACKEND=rustdar
export RADAR_RENDER_PATH=/path/to/radar-render
export NEXRAD_RENDER_PATH=/path/to/nexrad-render-cli

# (Optional) Set ECAPE runner path if not at ~/ecape-rs/target/release/
export ECAPE_RS_RUNNER=/path/to/run_case
```

## Timings

| Operation | Time |
|-----------|------|
| Model image render (Rust) | ~177ms |
| 22 maps including download | ~18s |
| 15 maps from cache | ~3.1s |
| Radar image (NEXRAD L2) | ~3s (download + render) |
| Sounding (40 levels + params) | ~15s (download-heavy) |
| METAR lookup | ~300ms |

## File Structure

```
~/.hermes/plugins/weather/
â”œâ”€â”€ plugin.yaml          # Hermes plugin manifest
â”œâ”€â”€ __init__.py          # register(ctx) â€” wires 13 tools
â”œâ”€â”€ schemas.py           # Tool schemas (what the LLM sees)
â”œâ”€â”€ nws.py               # NWS/METAR/SPC/Open-Meteo API client
â”œâ”€â”€ skill.md             # Usage guide for the LLM
â”œâ”€â”€ tools/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ data.py          # NWS API handlers
â”‚   â”œâ”€â”€ images.py        # Rust renderer + radar handlers
â”‚   â””â”€â”€ calc.py          # metrust calculations + sounding + ecape-rs bridge
â””â”€â”€ README.md
```

## Credits

- **Color tables**: [Solarpower07](https://github.com/Solarpower07) -- discrete color palettes and product style definitions used for all model imagery
- **Meteorological calculations**: metrust -- 205 functions verified against MetPy test suites
- **Plugin platform**: [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research

