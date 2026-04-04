# Hermes Weather Plugin

Weather plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent). 13 tools covering current conditions, forecasts, alerts, model imagery, radar, and meteorological calculations.

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
| `wx_model_image` | NWP field rendered as PNG -- 22+ products, 3 models, batch support |
| `wx_radar_image` | NEXRAD Level 2 reflectivity PPI (1024px, 200km range, 10 dBZ noise floor, dark background) |
| `wx_storm_image` | Radar with storm cell analysis overlaid |

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

## Supported Models

| Model | Resolution | Frequency | Forecast Range |
|-------|-----------|-----------|----------------|
| HRRR | 3 km | Hourly | 0-48h |
| NAM | 12 km | 6-hourly | 0-84h |
| RAP | 13 km | Hourly | 0-51h |

## Sounding Parameters

`wx_sounding` downloads pressure-level data and computes:

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

## Stack

```
Plugin (Python)
  ├── Data: requests → NWS / SPC / METAR / Open-Meteo APIs
  ├── Model images: rusbie → cfrust → wrf-render
  │                  (download)  (decode)  (rasterize)
  ├── Radar: radar-render binary (rustdar)
  └── Calculations: metrust-py (205 functions, PyO3 → Rust)
```

No eccodes, no Fortran, no C libraries in the Rust components. The only system dependency is a working Python environment.

## Python Packages

```
metrust      — 205 meteorological calculations (PyO3 → Rust)
cfrust       — GRIB2 decoder (pure Rust, replaces cfgrib/eccodes)
rusbie       — NWP downloader with byte-range .idx filtering
rustweather  — Plotting wrapper
rustplots    — MetPy-compatible plotting
wrf-rust     — Solarpower07 color tables + rasterizer
```

## Rust Binary

```
radar-render — NEXRAD Level 2 download + parse + render (from rustdar)
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

# (Optional) Set radar binary path if not at ~/rustdar/
export RADAR_RENDER_PATH=/path/to/radar-render

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
├── plugin.yaml          # Hermes plugin manifest
├── __init__.py          # register(ctx) — wires 13 tools
├── schemas.py           # Tool schemas (what the LLM sees)
├── nws.py               # NWS/METAR/SPC/Open-Meteo API client
├── skill.md             # Usage guide for the LLM
├── tools/
│   ├── __init__.py
│   ├── data.py          # NWS API handlers
│   ├── images.py        # Rust renderer + radar handlers
│   └── calc.py          # metrust calculations + sounding + ecape-rs bridge
└── README.md
```

## Credits

- **Color tables**: [Solarpower07](https://github.com/Solarpower07) -- discrete color palettes and product style definitions used for all model imagery
- **Meteorological calculations**: metrust -- 205 functions verified against MetPy test suites
- **Plugin platform**: [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research
