# Hermes Weather Plugin

Weather plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

It provides 13 tools for observations, forecasts, alerts, model imagery, radar, soundings, calculations, and ECAPE. The plugin is packaged for Hermes plugin autodiscovery and bootstraps its Rust backends on first use instead of requiring users to clone and build multiple repos by hand.

## Install

```bash`r`npip install git+https://github.com/FahrenheitResearch/hermes-weather-plugin.git`r`n```

Then start Hermes normally:

```bash
hermes
```

Hermes should auto-discover the plugin through the Python entry point.

## Runtime model

The plugin is Python-first, but several heavy paths use Rust binaries or Rust-backed Python packages.

- Data tools call NWS, SPC, METAR, and Open-Meteo directly from Python.
- `wx_model_image` uses `rusbie` for model access, tries the newer `wrf-rust` render path first, and falls back to `rustweather` where needed for GRIB model-map rendering.
- `wx_radar_image` and `wx_storm_image` use a radar backend binary.
- `wx_ecape` uses the `ecape-rs` runner.
- `wx_calc` and `wx_sounding` use `metrust` in-process.

If a required Rust binary is missing, the plugin will try to build it on first use into:

- `~/.hermes/weather/bin`

and cache downloaded source/build work under:

- `~/.hermes/weather/src`

## First-use bootstrap

The plugin can bootstrap these binaries automatically:

- `radar-render` from `rustdar`
- `run_case` from `ecape-rs`
- bundled `nexrad-render-cli`

This requires a working Rust toolchain (`cargo`, `rustc`) on the user machine unless they point the plugin at prebuilt binaries.

If you already have binaries installed, set optional overrides:

```bash
export RADAR_BACKEND=rustdar
export RADAR_RENDER_PATH=/path/to/radar-render
export NEXRAD_RENDER_PATH=/path/to/nexrad-render-cli
export ECAPE_RS_RUNNER=/path/to/run_case
```

Windows PowerShell:

```powershell
$env:RADAR_BACKEND = 'rustdar'
$env:RADAR_RENDER_PATH = 'C:\path\to\radar-render.exe'
$env:NEXRAD_RENDER_PATH = 'C:\path\to\nexrad-render-cli.exe'
$env:ECAPE_RS_RUNNER = 'C:\path\to\run_case.exe'
```

## Tools

### Data

| Tool | What it returns |
|------|-----------------|
| `wx_conditions` | Current observed conditions |
| `wx_forecast` | NWS 7-day or hourly forecast |
| `wx_alerts` | Active NWS alerts |
| `wx_metar` | Raw and decoded METAR |
| `wx_brief` | Conditions + short forecast + alert count |
| `wx_global` | Global weather via Open-Meteo |
| `wx_severe` | SPC categorical outlook + active watches |

### Images

| Tool | What it returns |
|------|-----------------|
| `wx_model_image` | Model field PNG rendered with `wrf-rust` |
| `wx_radar_image` | NEXRAD Level 2 radar image through the configured radar backend |
| `wx_storm_image` | Reflectivity image with storm-analysis overlays and metadata |

### Calculations

| Tool | What it returns |
|------|-----------------|
| `wx_calc` | Rust-backed meteorological calculations through `metrust` |
| `wx_sounding` | Model sounding plus derived parameters |
| `wx_ecape` | ECAPE, NCAPE, CAPE, CIN, LFC, EL, storm motion, optional parcel path |

## Model support

Verified model subsets currently exposed in Hermes:

- `wx_model_image`
  - `aigfs`, `gdas`, `gefs`, `gfs`, `graphcast`, `hiresw`, `hrrr`, `hrrrak`, `nam`, `nbm`, `rap`
- `wx_sounding`
  - `gdas`, `gfs`, `graphcast`, `hrrr`, `hrrrak`, `rrfs`
- `wx_ecape`
  - same verified profile subset as `wx_sounding`

Models outside those sets may exist lower in the backend stack, but they are not exposed until their Hermes extraction path is verified.

## Radar

Hermes keeps a stable radar tool contract and routes it through the configured radar backend.

Current backends:

- `rustdar` (default)
- `nexrad`

Supported radar products:

- both backends: `ref`, `vel`, `sw`, `zdr`, `rho`, `phi`
- `rustdar` only: `srv`, `vil`

## Soundings and ECAPE

`wx_sounding` downloads a verified model pressure-level profile and computes:

- CAPE/CIN: surface-based, mixed-layer, most-unstable
- LCL/LFC/EL
- LI, K-index, Total Totals
- bulk shear and SRH
- precipitable water, lapse rates, freezing level
- standard pressure-level profile output

`wx_ecape` runs the parity-verified `ecape-rs` runner on the same profile.

Defaults:

- `cape_type=most_unstable`
- `storm_motion_type=right_moving`
- `pseudoadiabatic=true`

Supported storm-motion modes:

- `right_moving`
- `left_moving`
- `mean_wind`
- `user_defined`

Set `include_parcel_profile=true` to return the aligned parcel path arrays.

## Packaging notes

This package is intended to be installed with `pip` from GitHub, not copied manually into `~/.hermes/plugins`.

The package exposes the Hermes plugin entry point directly, ships `plugin.yaml`, ships the bundled `nexrad-render-cli` source, installs the bundled skill on first load, and bootstraps Rust binaries on demand.

## Stack

```text
Plugin (Python)
  |- Data: requests -> NWS / SPC / METAR / Open-Meteo APIs
  |- Model images: rusbie -> wrf-rust
  |- Radar: rustdar or bundled nexrad-render-cli
  `- Calculations: metrust + ecape-rs
```

## Dependencies

Python package dependencies:

- `requests`
- `numpy`
- `metrust`
- `rusbie`
- `rustweather`
- `wrf-rust`

Optional system dependency for first-use binary builds:

- Rust toolchain (`cargo`, `rustc`)

## Credits

- [Solarpower07](https://github.com/Solarpower07) for model imagery color tables and product styling
- `metrust` for Rust-backed meteorological calculations
- `ecape-rs` for the parity-verified ECAPE runner
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research

