"""Tier 2 — Image tool handlers. rustweather for model maps, radar-render for NEXRAD."""

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# radar-render binary path
_EXE = ".exe" if os.name == "nt" else ""
RADAR_RENDER = os.environ.get(
    "RADAR_RENDER_PATH",
    str(Path.home() / "rustdar" / "target" / "release" / f"radar-render{_EXE}")
)

_IMG_DIR = Path.home() / ".hermes" / "weather" / "images"
_IMG_DIR.mkdir(parents=True, exist_ok=True)


def check_radar_render():
    return os.path.isfile(RADAR_RENDER)


def check_rustweather():
    try:
        import rustweather
        return True
    except ImportError:
        return False


def _build_rgba_palette(cmap_name):
    """Build RGBA color list from solar7 composite color definitions."""
    from wrf.solar7 import _COMPOSITE_SEGS, _COMPOSITE_QUANTS, _lerp_colors
    from wrf.solar7 import (
        _WINDS_COLORS, _TEMPERATURE_COLORS, _REFLECTIVITY_COLORS,
        _DEWPOINT_DRY, _DEWPOINT_MOIST_SEGS,
        _RH_SEG1_COLORS, _RH_SEG2_COLORS, _RH_SEG3_COLORS,
        _RELVORT_COLORS, _GEOPOT_ANOMALY_COLORS,
        _SIM_IR_SEG_COOL, _SIM_IR_SEG_WARM, _SIM_IR_SEG_GRAY,
        _PRECIP_SEGS,
    )
    import numpy as np

    key = cmap_name.replace("solar7_", "")

    # Composite palettes
    if key in _COMPOSITE_QUANTS:
        colors = []
        for seg_colors, n in zip(_COMPOSITE_SEGS, _COMPOSITE_QUANTS[key]):
            if n > 0:
                colors.extend(_lerp_colors(seg_colors, n))
        return [(int(r*255), int(g*255), int(b*255), 255) for r,g,b in colors]

    def _hex_to_rgba(hex_list):
        def h2r(h):
            h = h.lstrip("#")
            return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)
        return [(int(r*255), int(g*255), int(b*255), 255) for r,g,b in [h2r(c) for c in hex_list]]

    # Named continuous palettes
    builders = {
        "winds": lambda: _lerp_colors(_WINDS_COLORS, 60),
        "temperature": lambda: _lerp_colors(_TEMPERATURE_COLORS, 180),
        "dewpoint": lambda: (
            _lerp_colors(_DEWPOINT_DRY, 80) +
            sum([_lerp_colors(s, n) for s, n in _DEWPOINT_MOIST_SEGS], [])
        ),
        "rh": lambda: (
            _lerp_colors(_RH_SEG1_COLORS, 40) +
            _lerp_colors(_RH_SEG2_COLORS, 50) +
            _lerp_colors(_RH_SEG3_COLORS, 10)
        ),
        "relvort": lambda: _lerp_colors(_RELVORT_COLORS, 100),
        "geopot_anomaly": lambda: _lerp_colors(_GEOPOT_ANOMALY_COLORS, 100),
        "sim_ir": lambda: (
            _lerp_colors(_SIM_IR_SEG_COOL, 10) +
            _lerp_colors(_SIM_IR_SEG_WARM, 60) +
            _lerp_colors(_SIM_IR_SEG_GRAY, 60)
        ),
        "precip": lambda: sum(
            [_lerp_colors(seg, n) for seg, n in _PRECIP_SEGS], []
        ),
    }

    # Discrete palettes
    if key == "reflectivity":
        return _hex_to_rgba(_REFLECTIVITY_COLORS)

    if key in builders:
        colors = builders[key]()
        return [(int(r*255), int(g*255), int(b*255), 255) for r,g,b in colors]

    return None


def _render_with_rust(data, lat, lon, product_key, title, out_path):
    """Render a GRIB field using wrf-render (Rust) with solar7 styling."""
    import numpy as np
    from wrf._wrf import render_grib
    from wrf.solar7 import SOLAR7_STYLES

    style = SOLAR7_STYLES.get(product_key)
    if not style:
        return False

    levels = style.get("levels")
    if levels is None or len(levels) < 2:
        return False
    levels = list(levels.astype(float))

    cmap_name = style.get("cmap", "solar7_cape")
    rgba = _build_rgba_palette(cmap_name)
    if not rgba:
        return False

    # Resample colors to match number of level intervals
    n_intervals = len(levels) - 1
    indices = np.linspace(0, len(rgba)-1, n_intervals).astype(int)
    rgba_resampled = [rgba[i] for i in indices]

    mask_below = float(levels[0]) if levels[0] > 0 else None

    png = render_grib(
        data.astype(np.float64),
        lat.astype(np.float64),
        lon.astype(np.float64),
        levels,
        rgba_resampled,
        title=title,
        borders=True,
        mask_below=mask_below,
        over_color=rgba[-1],
        under_color=(0, 0, 0, 0),
        width=1200,
        height=900,
        colorbar=True,
    )

    with open(out_path, "wb") as f:
        f.write(png)
    return True


def wx_model_image(args: dict, **kwargs) -> str:
    var_raw = args.get("var")
    if not var_raw:
        return json.dumps({"error": "var is required"})

    # Support comma-separated variables for batch rendering
    vars_list = [v.strip() for v in var_raw.split(",") if v.strip()]
    if not vars_list:
        return json.dumps({"error": "var is required"})

    try:
        from rustweather import plot

        # Build date string for cycle selection
        date_str = None
        if args.get("cycle") is not None:
            date_part = args.get("date", "")
            if date_part:
                d = date_part
                date_str = f"{d[:4]}-{d[4:6]}-{d[6:8]} {args['cycle']:02d}:00"
            else:
                from datetime import datetime, timezone
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                date_str = f"{today} {args['cycle']:02d}:00"

        # Build area tuple for regional zoom
        area = "conus"
        if args.get("lat") is not None and args.get("lon") is not None:
            r = args.get("radius_km", 500)
            deg = r / 111.0
            lat, lon = args["lat"], args["lon"]
            area = (lon - deg, lon + deg, lat - deg, lat + deg)

        model_name = args.get("model", "hrrr")
        fhour = args.get("fhour", 0)
        results = []

        # Resolve to latest cycle with the requested fhour available
        if not date_str:
            from rusbie import Herbie as _RH
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            _now = _dt.now(_tz.utc)
            for _lb in range(0, 8):
                _hour = (_now.hour - _lb) % 24
                _d = _now if _hour <= _now.hour else _now - _td(days=1)
                _ds = _d.strftime("%Y-%m-%d") + f" {_hour:02d}:00"
                try:
                    _h = _RH(_ds, model=model_name, fxx=fhour)
                    if _h.grib_source:
                        date_str = _ds
                        break
                except Exception:
                    continue

        # Alias → (solar7_key, scientific_title, units)
        _PRODUCT_META = {
            "cape":        ("cape",     "Surface-Based CAPE",                    "J/kg"),
            "mlcape":      ("mlcape",   "Mixed-Layer CAPE (0-90 mb)",            "J/kg"),
            "mucape":      ("mucape",   "Most-Unstable CAPE",                    "J/kg"),
            "sbcape":      ("sbcape",   "Surface-Based CAPE",                    "J/kg"),
            "cin":         ("cin",      "Surface-Based CIN",                     "J/kg"),
            "mlcin":       ("mlcin",    "Mixed-Layer CIN (0-90 mb)",             "J/kg"),
            "refl":        ("dbz",      "Composite Reflectivity",                "dBZ"),
            "reflectivity":("dbz",      "Composite Reflectivity",                "dBZ"),
            "temp":        ("temp",     "2-m Temperature",                       "F"),
            "temperature": ("temp",     "2-m Temperature",                       "F"),
            "dewpoint":    ("dp2m",     "2-m Dewpoint Temperature",              "F"),
            "td":          ("dp2m",     "2-m Dewpoint Temperature",              "F"),
            "rh":          ("rh2m",     "2-m Relative Humidity",                 "%"),
            "relative_humidity": ("rh2m", "2-m Relative Humidity",               "%"),
            "gust":        ("wspd10",   "Surface Wind Gust",                     "m/s"),
            "wind":        ("wspd10",   "10-m Wind Speed",                       "m/s"),
            "srh":         ("srh",      "0-3 km Storm-Relative Helicity",        "m^2/s^2"),
            "srh01":       ("srh1",     "0-1 km Storm-Relative Helicity",        "m^2/s^2"),
            "srh03":       ("srh3",     "0-3 km Storm-Relative Helicity",        "m^2/s^2"),
            "helicity":    ("srh3",     "0-3 km Storm-Relative Helicity",        "m^2/s^2"),
            "uh":          ("uhel",     "2-5 km Updraft Helicity (hourly max)",   "m^2/s^2"),
            "updraft_helicity": ("uhel","2-5 km Updraft Helicity (hourly max)",   "m^2/s^2"),
            "pwat":        ("pw",       "Precipitable Water",                    "kg/m^2"),
            "precipitable_water": ("pw","Precipitable Water",                    "kg/m^2"),
            "precip":      ("precip",   "Total Precipitation",                   "mm"),
            "precipitation":("precip",  "Total Precipitation",                   "mm"),
            "mslp":        ("slp",      "Mean Sea Level Pressure",               "hPa"),
            "pressure":    ("slp",      "Mean Sea Level Pressure",               "hPa"),
            "heights_500": ("height",   "500 mb Geopotential Height",            "gpm"),
            "vorticity_500":("avo",     "500 mb Absolute Vorticity",             "1/s"),
            "stp":         ("stp",      "Significant Tornado Parameter",         ""),
            "scp":         ("scp",      "Supercell Composite Parameter",         ""),
            "ehi":         ("ehi",      "Energy-Helicity Index",                 ""),
            "bulk_shear":  ("bulk_shear","0-6 km Bulk Wind Shear",               "m/s"),
            "shear_0_6km": ("shear_0_6km","0-6 km Bulk Wind Shear",             "1/s"),
            "shear_0_1km": ("shear_0_1km","0-1 km Bulk Wind Shear",             "1/s"),
            "cape3d":      ("cape3d",   "0-3 km CAPE",                           "J/kg"),
            "cloud":       ("cloudfrac","Total Cloud Cover",                     "%"),
        }

        for var in vars_list:
            path = str(_IMG_DIR / f"model_{var}_{model_name}_f{fhour}_{os.getpid()}.png")
            try:
                rust_ok = False

                # Try Rust renderer (fast, Solarpower07 color tables)
                meta = _PRODUCT_META.get(var.lower())
                solar_key = meta[0] if meta else None
                if solar_key:
                    try:
                        from rusbie import Herbie as RH
                        from rustweather.models import FIELD_ALIASES
                        import numpy as np

                        grib_search = FIELD_ALIASES.get(var.lower(), var)
                        H_dl = RH(model=model_name, fxx=fhour, date=date_str)
                        ds = H_dl.xarray(grib_search, verbose=False)
                        vname = list(ds.data_vars)[0]
                        data = ds[vname].values
                        lat_arr = ds.latitude.values
                        lon_arr = ds.longitude.values

                        # Handle 1D lat/lon (regular grids like GFS) — meshgrid to 2D
                        if lat_arr.ndim == 1 and lon_arr.ndim == 1:
                            lon_arr, lat_arr = np.meshgrid(lon_arr, lat_arr)

                        # Build scientific title
                        product_name = meta[1] if meta else var
                        units = meta[2] if meta else ""
                        units_str = f" ({units})" if units else ""
                        init_str = date_str.replace(" ", " ").replace(":00", "z") if date_str else ""
                        title = f"{model_name.upper()} {init_str} | F{fhour:03d} | {product_name}{units_str}"

                        rust_ok = _render_with_rust(
                            data, lat_arr, lon_arr, solar_key, title, path
                        )
                    except Exception as e:
                        logger.debug("Rust render failed for %s: %s", var, e)

                # Fallback to rustweather/matplotlib
                if not rust_ok:
                    plot(
                        model=model_name, search=var, fxx=fhour,
                        date=date_str, area=area, save=path,
                    )

                if os.path.isfile(path):
                    results.append({
                        "image_path": path,
                        "image_file": os.path.basename(path),
                        "variable": var,
                    })
                else:
                    results.append({"variable": var, "error": "no image produced"})
            except Exception as e:
                results.append({"variable": var, "error": str(e)})

        return json.dumps({
            "model": model_name.upper(),
            "forecast_hour": fhour,
            "images": results,
            "count": len([r for r in results if "image_path" in r]),
        })
    except Exception as e:
        return json.dumps({"error": f"model image failed: {type(e).__name__}: {e}"})


def wx_radar_image(args: dict, **kwargs) -> str:
    cmd = [RADAR_RENDER]

    if args.get("site"):
        cmd.extend(["--site", args["site"].upper()])
    elif args.get("lat") is not None and args.get("lon") is not None:
        cmd.extend(["--lat", str(args["lat"]), "--lon", str(args["lon"])])
    else:
        return json.dumps({"error": "Provide site or lat/lon"})

    if args.get("product"):
        cmd.extend(["--product", args["product"]])

    size = args.get("size", 1024)
    cmd.extend(["--size", str(size)])

    min_dbz = args.get("min_dbz", 10)
    cmd.extend(["--min-dbz", str(min_dbz)])

    range_km = args.get("range_km", 200)
    cmd.extend(["--range-km", str(range_km)])

    # Output to temp dir
    out_path = str(_IMG_DIR / f"radar_{args.get('site', 'auto')}_{os.getpid()}.png")
    cmd.extend(["-o", out_path])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            err = result.stderr.strip()
            return json.dumps({"error": err or f"radar-render exited {result.returncode}"})

        stdout = result.stdout.strip()
        if not stdout:
            return json.dumps({"error": "radar-render returned no output"})

        data = json.loads(stdout)
        data["image_file"] = os.path.basename(data.get("image_path", ""))
        return json.dumps(data)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "radar-render timed out (60s)"})
    except FileNotFoundError:
        return json.dumps({"error": f"radar-render not found at {RADAR_RENDER}"})
    except Exception as e:
        return json.dumps({"error": f"radar image failed: {e}"})


def wx_storm_image(args: dict, **kwargs) -> str:
    # Same as radar but could add --storm-cells flag when available
    site = args.get("site")
    if not site:
        return json.dumps({"error": "site is required"})
    # For now, render radar with cell detection markers
    return wx_radar_image({"site": site, "product": "ref", "size": 1024, "min_dbz": 10}, **kwargs)
