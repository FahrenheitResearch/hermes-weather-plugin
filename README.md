# Hermes Weather Plugin

A native [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that provides real-time weather data, NWS-grade model imagery, NEXRAD radar, and verified meteorological calculations. Built entirely on a Rust-backed weather stack — no legacy dependencies.

## What It Does

Ask Hermes natural language weather questions and it calls the right tools:

- **"How's the weather in Portland?"** → current conditions from NWS API
- **"Show me the radar near OKC"** → NEXRAD Level 2 radar PNG (1024px, 200km, noise-filtered)
- **"Show me CAPE and SRH on the latest HRRR f18"** → two NWS-grade model maps in one call
- **"Calculate the LCL for 30°C and 20°C dewpoint at 1000mb"** → verified metrust calculation
- **"Get me a sounding for Oklahoma City"** → 40-level profile with CAPE, CIN, SRH, shear, LCL, STP

## 12 Tools

### Data (Python → NWS API)
| Tool | Description |
|------|-------------|
| `wx_conditions` | Current observations (temperature, wind, sky, dewpoint) |
| `wx_forecast` | NWS 7-day or hourly forecast |
| `wx_alerts` | Active warnings, watches, advisories |
| `wx_metar` | Raw/decoded METAR for any ICAO station |
| `wx_brief` | Quick briefing (conditions + forecast + alert count) |
| `wx_global` | Global weather via Open-Meteo (non-US locations) |
| `wx_severe` | SPC Day 1 categorical outlook + active watches |

### Visualization (Rust)
| Tool | Description |
|------|-------------|
| `wx_model_image` | NWP model field rendered as PNG — 22+ products, 3 models, batch support |
| `wx_radar_image` | NEXRAD Level 2 radar PPI — high-res, dark background, dBZ filtering |
| `wx_storm_image` | Radar with storm cell analysis |

### Calculations (metrust, Rust-backed)
| Tool | Description |
|------|-------------|
| `wx_calc` | 205 verified meteorological functions (dewpoint, CAPE, LCL, wind chill, etc.) |
| `wx_sounding` | Model sounding at a point — 40 levels + all derived severe weather parameters |

## Model Image Products

22+ fields with NWS Solarpower07 color tables, state borders, colorbars, scientific titles:

**Instability**: CAPE (surface, mixed-layer, most-unstable, 0-3km), CIN
**Shear/Helicity**: SRH 0-1km, SRH 0-3km, updraft helicity, 0-6km bulk shear, 0-1km bulk shear
**Surface**: Temperature, dewpoint, RH, wind gust, cloud cover, precipitation, visibility
**Composites**: Significant Tornado Parameter (STP), Supercell Composite (SCP), Energy-Helicity Index (EHI)
**Reflectivity**: Composite reflectivity (NWS 27-color discrete palette)

Comma-separated batch: `"cape,srh,uh,stp"` generates 4 images in one tool call.

## Verified Models

| Model | Resolution | Frequency | Forecast Range |
|-------|-----------|-----------|----------------|
| **HRRR** | 3 km | Hourly | 0-48h |
| **NAM** | 12 km | 6-hourly | 0-84h |
| **RAP** | 13 km | Hourly | 0-51h |

## Sounding Parameters

The `wx_sounding` tool downloads pressure-level data and computes:

- **CAPE/CIN**: Surface-based, mixed-layer, most-unstable
- **Levels**: LCL (pressure, temperature, height AGL), LFC, EL
- **Indices**: Lifted Index, K-Index, Total Totals
- **Shear**: 0-1km and 0-6km bulk shear, SRH 0-1km and 0-3km
- **Storm motion**: Bunkers right-mover
- **Composites**: STP (fixed-layer)
- **Moisture**: Precipitable water, freezing level
- **Lapse rates**: 0-3km, 700-500mb
- **Profile**: Standard levels (1000, 925, 850, 700, 500, 300, 250 mb) with T, Td, wind

## Stack

```
Plugin (Python)
  ├── Data: requests → NWS / SPC / METAR / Open-Meteo APIs
  ├── Model images: rusbie → cfrust → wrf-render
  │                  (download)  (decode)  (Rust rasterizer)
  ├── Radar: radar-render binary (rustdar library)
  └── Calculations: metrust-py (205 functions, PyO3 → Rust)
```

All rendering uses the Solarpower07 color table library with Lambert Conformal projection, state/country borders, and proper colorbars. Average render time: **177ms per image**.

**No matplotlib in the rendering path.** Pure Rust rasterization via wrf-render.

## Dependencies

### Python packages (all Rust-backed)
```
metrust    — 205 verified meteorological calculations
cfrust     — Pure Rust GRIB2 decoder (replaces cfgrib/eccodes)
rusbie     — 45-model NWP downloader with byte-range .idx filtering
rustweather — One-liner plotting wrapper
rustplots   — MetPy-compatible plotting
wrf-rust    — Solarpower07 color tables + Rust rasterizer
```

### Rust binary
```
radar-render — NEXRAD Level 2 download + parse + render (from rustdar)
```

## Setup

```bash
# 1. Install Python packages
pip install metrust cfrust rusbie rustweather

# 2. Install from source (not yet on PyPI)
pip install -e /path/to/rustplots
pip install -e /path/to/wrf-rust

# 3. Build radar binary
cd /path/to/rustdar
cargo build --release --bin radar-render

# 4. Copy plugin to Hermes
cp -r weather ~/.hermes/plugins/

# 5. (Optional) Set radar binary path if not at ~/rustdar/
export RADAR_RENDER_PATH=/path/to/radar-render
```

## Benchmarks

| Metric | Value |
|--------|-------|
| Model image render (Rust) | **177ms avg** |
| 22 NWS-grade maps | **18s total** (incl. download) |
| 15 maps from cache | **3.1s total** |
| Radar image (NEXRAD L2) | **~3s** (download + render) |
| Sounding (40 levels + params) | **~15s** (download-heavy) |
| METAR lookup | **~300ms** |

## File Structure

```
~/.hermes/plugins/weather/
├── plugin.yaml          # Hermes plugin manifest
├── __init__.py          # register(ctx) — wires 12 tools
├── schemas.py           # Tool schemas (what the LLM sees)
├── nws.py               # NWS/METAR/SPC/Open-Meteo API client
├── skill.md             # Bundled skill (usage guide for the LLM)
├── tools/
│   ├── __init__.py
│   ├── data.py          # Tier 1: NWS API handlers
│   ├── images.py        # Tier 2: Rust renderer + radar handlers
│   └── calc.py          # Tier 3: metrust calculations + sounding
└── README.md
```

## Credits

- **Color Tables**: Solarpower07 — NWS-grade discrete color palettes and product style definitions
- **Meteorological calculations**: metrust — 205 functions verified against MetPy test suites
- **Plugin platform**: [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research
