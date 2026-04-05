"""Tier 2 - Image tool handlers."""

import json
import logging
import os
import subprocess
from pathlib import Path

from .. import bootstrap
from ..model_support import resolve_image_search

logger = logging.getLogger(__name__)
_IMG_DIR = Path.home() / ".hermes" / "weather" / "images"
_IMG_DIR.mkdir(parents=True, exist_ok=True)


def _radar_backend_name() -> str:
    return os.environ.get("RADAR_BACKEND", "rustdar").strip().lower() or "rustdar"


def check_radar_render():
    path, _ = bootstrap.ensure_radar_binary(_radar_backend_name(), auto_build=False)
    return bool(path)


def _build_rgba_palette(cmap_name):
    from wrf.solar7 import _COMPOSITE_SEGS, _COMPOSITE_QUANTS, _lerp_colors
    from wrf.solar7 import _WINDS_COLORS, _TEMPERATURE_COLORS, _REFLECTIVITY_COLORS
    from wrf.solar7 import _DEWPOINT_DRY, _DEWPOINT_MOIST_SEGS, _RH_SEG1_COLORS, _RH_SEG2_COLORS, _RH_SEG3_COLORS
    from wrf.solar7 import _RELVORT_COLORS, _GEOPOT_ANOMALY_COLORS, _SIM_IR_SEG_COOL, _SIM_IR_SEG_WARM, _SIM_IR_SEG_GRAY
    from wrf.solar7 import _PRECIP_SEGS

    key = cmap_name.replace("solar7_", "")
    if key in _COMPOSITE_QUANTS:
        colors = []
        for seg_colors, n in zip(_COMPOSITE_SEGS, _COMPOSITE_QUANTS[key]):
            if n > 0:
                colors.extend(_lerp_colors(seg_colors, n))
        return [(int(r * 255), int(g * 255), int(b * 255), 255) for r, g, b in colors]

    def _hex_to_rgba(hex_list):
        def h2r(h):
            h = h.lstrip("#")
            return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)
        return [(int(r * 255), int(g * 255), int(b * 255), 255) for r, g, b in [h2r(c) for c in hex_list]]

    builders = {
        "winds": lambda: _lerp_colors(_WINDS_COLORS, 60),
        "temperature": lambda: _lerp_colors(_TEMPERATURE_COLORS, 180),
        "dewpoint": lambda: _lerp_colors(_DEWPOINT_DRY, 80) + sum([_lerp_colors(s, n) for s, n in _DEWPOINT_MOIST_SEGS], []),
        "rh": lambda: _lerp_colors(_RH_SEG1_COLORS, 40) + _lerp_colors(_RH_SEG2_COLORS, 50) + _lerp_colors(_RH_SEG3_COLORS, 10),
        "relvort": lambda: _lerp_colors(_RELVORT_COLORS, 100),
        "geopot_anomaly": lambda: _lerp_colors(_GEOPOT_ANOMALY_COLORS, 100),
        "sim_ir": lambda: _lerp_colors(_SIM_IR_SEG_COOL, 10) + _lerp_colors(_SIM_IR_SEG_WARM, 60) + _lerp_colors(_SIM_IR_SEG_GRAY, 60),
        "precip": lambda: sum([_lerp_colors(seg, n) for seg, n in _PRECIP_SEGS], []),
    }
    if key == "reflectivity":
        return _hex_to_rgba(_REFLECTIVITY_COLORS)
    if key in builders:
        colors = builders[key]()
        return [(int(r * 255), int(g * 255), int(b * 255), 255) for r, g, b in colors]
    return None


def _render_with_rust(data, lat, lon, product_key, title, out_path):
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
    rgba = _build_rgba_palette(style.get("cmap", "solar7_cape"))
    if not rgba:
        return False
    n_intervals = len(levels) - 1
    indices = np.linspace(0, len(rgba) - 1, n_intervals).astype(int)
    rgba_resampled = [rgba[i] for i in indices]
    mask_below = float(levels[0]) if levels[0] > 0 else None
    png = render_grib(
        data.astype(np.float64), lat.astype(np.float64), lon.astype(np.float64), levels, rgba_resampled,
        title=title, borders=True, mask_below=mask_below, over_color=rgba[-1], under_color=(0, 0, 0, 0),
        width=1200, height=900, colorbar=True,
    )
    with open(out_path, "wb") as f:
        f.write(png)
    return True


def _extract_grid(ds):
    import numpy as np

    vname = list(ds.data_vars)[0]
    data = ds[vname].values.astype(np.float64)
    lat_arr = ds.latitude.values
    lon_arr = ds.longitude.values
    if lat_arr.ndim == 1 and lon_arr.ndim == 1:
        lon_arr, lat_arr = np.meshgrid(lon_arr, lat_arr)
    return data, lat_arr, lon_arr


def _region_area(lat, lon, radius_km):
    if lat is None or lon is None:
        return "conus"
    deg = float(radius_km) / 111.0
    return (lon - deg, lon + deg, lat - deg, lat + deg)


def _download_scalar(H, search):
    ds = H.xarray(search, verbose=False, remove_grib=False)
    return _extract_grid(ds)


def _crop_to_region(data, lat_arr, lon_arr, lat, lon, radius_km):
    import numpy as np

    if lat is None or lon is None:
        return data, lat_arr, lon_arr

    lat_pad = float(radius_km) / 111.0
    lon_pad = float(radius_km) / max(111.0 * np.cos(np.deg2rad(lat)), 1e-6)
    lon_grid = lon_arr.copy()
    if np.nanmax(lon_grid) > 180:
        lon_grid = np.where(lon_grid > 180, lon_grid - 360, lon_grid)

    mask = (
        (lat_arr >= lat - lat_pad) & (lat_arr <= lat + lat_pad) &
        (lon_grid >= lon - lon_pad) & (lon_grid <= lon + lon_pad)
    )
    if not np.any(mask):
        return data, lat_arr, lon_arr

    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return data, lat_arr, lon_arr
    r0, r1 = rows[0], rows[-1] + 1
    c0, c1 = cols[0], cols[-1] + 1
    return data[r0:r1, c0:c1], lat_arr[r0:r1, c0:c1], lon_arr[r0:r1, c0:c1]


def _load_plot_data(H, var, model_name):
    import numpy as np

    def _download_first_available(search_options):
        if isinstance(search_options, str):
            search_options = [search_options]
        errors = []
        for search_str in search_options:
            try:
                return _download_scalar(H, search_str)
            except Exception as exc:
                errors.append(f"{search_str}: {exc}")
        raise RuntimeError("; ".join(errors))

    composites = {
        "stp": {
            "cape": ["CAPE:surface"],
            "srh": ["HLCY:1000-0 m above ground", "HLCY:1000-0 m above ground level"],
            "shear_u": ["VUCSH:0-6000 m above ground", "VUCSH:0-6000 m above ground level"],
            "shear_v": ["VVCSH:0-6000 m above ground", "VVCSH:0-6000 m above ground level"],
            "cin": ["CIN:surface"],
        },
        "scp": {
            "cape": ["CAPE:surface"],
            "srh": ["HLCY:3000-0 m above ground", "HLCY:3000-0 m above ground level"],
            "shear_u": ["VUCSH:0-6000 m above ground", "VUCSH:0-6000 m above ground level"],
            "shear_v": ["VVCSH:0-6000 m above ground", "VVCSH:0-6000 m above ground level"],
        },
        "ehi": {
            "cape": ["CAPE:surface"],
            "srh": ["HLCY:1000-0 m above ground", "HLCY:1000-0 m above ground level"],
        },
    }
    if var in composites:
        fields, lat_arr, lon_arr = {}, None, None
        for key, search_options in composites[var].items():
            vals, lat_arr, lon_arr = _download_first_available(search_options)
            fields[key] = vals
        if var == "stp":
            shear_mag = np.sqrt(fields["shear_u"] ** 2 + fields["shear_v"] ** 2)
            cin_term = np.where(fields["cin"] > -50, 1.0, np.where(fields["cin"] < -200, 0.0, (200 + fields["cin"]) / 150.0))
            return np.clip(fields["cape"] / 1500.0, 0, None) * np.clip(fields["srh"] / 150.0, 0, None) * np.clip(shear_mag / 20.0, 0, 1.5) * cin_term, lat_arr, lon_arr
        if var == "scp":
            shear_mag = np.sqrt(fields["shear_u"] ** 2 + fields["shear_v"] ** 2)
            return np.clip(fields["cape"] / 1000.0, 0, None) * np.clip(fields["srh"] / 50.0, 0, None) * np.clip(shear_mag / 20.0, 0, 1.5), lat_arr, lon_arr
        return (fields["cape"] * fields["srh"]) / 160000.0, lat_arr, lon_arr

    resolved = resolve_image_search(var, model_name)
    parts = [p.strip() for p in resolved.split("|") if p.strip()]
    if len(parts) == 1:
        return _download_scalar(H, parts[0])
    u_vals, lat_arr, lon_arr = _download_scalar(H, parts[0])
    v_vals, _, _ = _download_scalar(H, parts[1])
    return np.sqrt(u_vals ** 2 + v_vals ** 2), lat_arr, lon_arr


def wx_model_image(args: dict, **kwargs) -> str:
    var_raw = args.get("var")
    if not var_raw:
        return json.dumps({"error": "var is required"})
    vars_list = [v.strip() for v in var_raw.split(",") if v.strip()]
    if not vars_list:
        return json.dumps({"error": "var is required"})

    try:
        from rusbie import Herbie as RH
        from datetime import datetime, timezone, timedelta

        date_str = None
        if args.get("cycle") is not None:
            date_part = args.get("date", "")
            if date_part:
                d = date_part
                date_str = f"{d[:4]}-{d[4:6]}-{d[6:8]} {args['cycle']:02d}:00"
            else:
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                date_str = f"{today} {args['cycle']:02d}:00"

        model_name = args.get("model", "hrrr")
        fhour = args.get("fhour", 0)
        lat = args.get("lat")
        lon = args.get("lon")
        radius_km = args.get("radius_km", 500)
        area = _region_area(lat, lon, radius_km)
        results = []

        if not date_str:
            now = datetime.now(timezone.utc)
            for lookback in range(0, 8):
                hour = (now.hour - lookback) % 24
                day = now if hour <= now.hour else now - timedelta(days=1)
                candidate = day.strftime("%Y-%m-%d") + f" {hour:02d}:00"
                try:
                    probe = RH(candidate, model=model_name, fxx=fhour)
                    if probe.grib_source:
                        date_str = candidate
                        break
                except Exception:
                    continue
        if not date_str:
            return json.dumps({"error": f"No available cycle found for model={model_name} fhour={fhour}"})

        product_meta = {
            "cape": ("cape", "Surface-Based CAPE", "J/kg"), "mlcape": ("mlcape", "Mixed-Layer CAPE (0-90 mb)", "J/kg"), "mucape": ("mucape", "Most-Unstable CAPE", "J/kg"), "sbcape": ("sbcape", "Surface-Based CAPE", "J/kg"),
            "cin": ("cin", "Surface-Based CIN", "J/kg"), "mlcin": ("mlcin", "Mixed-Layer CIN (0-90 mb)", "J/kg"), "refl": ("dbz", "Composite Reflectivity", "dBZ"), "reflectivity": ("dbz", "Composite Reflectivity", "dBZ"),
            "temp": ("temp", "2-m Temperature", "F"), "temperature": ("temp", "2-m Temperature", "F"), "dewpoint": ("dp2m", "2-m Dewpoint Temperature", "F"), "td": ("dp2m", "2-m Dewpoint Temperature", "F"),
            "rh": ("rh2m", "2-m Relative Humidity", "%"), "relative_humidity": ("rh2m", "2-m Relative Humidity", "%"), "gust": ("wspd10", "Surface Wind Gust", "m/s"), "wind": ("wspd10", "10-m Wind Speed", "m/s"),
            "srh": ("srh", "0-3 km Storm-Relative Helicity", "m^2/s^2"), "srh01": ("srh1", "0-1 km Storm-Relative Helicity", "m^2/s^2"), "srh03": ("srh3", "0-3 km Storm-Relative Helicity", "m^2/s^2"), "helicity": ("srh3", "0-3 km Storm-Relative Helicity", "m^2/s^2"),
            "uh": ("uhel", "2-5 km Updraft Helicity (hourly max)", "m^2/s^2"), "updraft_helicity": ("uhel", "2-5 km Updraft Helicity (hourly max)", "m^2/s^2"), "pwat": ("pw", "Precipitable Water", "kg/m^2"), "precipitable_water": ("pw", "Precipitable Water", "kg/m^2"),
            "precip": ("precip", "Total Precipitation", "mm"), "precipitation": ("precip", "Total Precipitation", "mm"), "mslp": ("slp", "Mean Sea Level Pressure", "hPa"), "pressure": ("slp", "Mean Sea Level Pressure", "hPa"),
            "heights_500": ("height", "500 mb Geopotential Height", "gpm"), "vorticity_500": ("avo", "500 mb Absolute Vorticity", "1/s"), "stp": ("stp", "Significant Tornado Parameter", ""), "scp": ("cape", "Supercell Composite Parameter", ""),
            "ehi": ("ehi", "Energy-Helicity Index", ""), "bulk_shear": ("wspd", "0-6 km Bulk Wind Shear", "m/s"), "shear_0_6km": ("wspd", "0-6 km Bulk Wind Shear", "m/s"), "shear_0_1km": ("wspd", "0-1 km Bulk Wind Shear", "m/s"),
            "cape3d": ("cape", "0-3 km CAPE", "J/kg"), "cloud": ("cloudfrac", "Total Cloud Cover", "%"), "cloud_cover": ("cloudfrac", "Total Cloud Cover", "%"),
        }

        H = RH(model=model_name, fxx=fhour, date=date_str)
        init_str = date_str.replace(":00", "z") if date_str else ""
        for var in vars_list:
            path = str(_IMG_DIR / f"model_{var}_{model_name}_f{fhour}_{os.getpid()}.png")
            try:
                meta = product_meta.get(var.lower())
                if not meta:
                    raise ValueError(f"Unsupported model image variable: {var}")
                solar_key, product_name, units = meta
                data, lat_arr, lon_arr = _load_plot_data(H, var.lower(), model_name)
                data, lat_arr, lon_arr = _crop_to_region(data, lat_arr, lon_arr, lat, lon, radius_km)
                units_str = f" ({units})" if units else ""
                region_str = f" | {lat:.2f},{lon:.2f} +/- {radius_km} km" if lat is not None and lon is not None else ""
                title = f"{model_name.upper()} {init_str} | F{fhour:03d} | {product_name}{units_str}{region_str}"
                if not _render_with_rust(data, lat_arr, lon_arr, solar_key, title, path):
                    raise RuntimeError(f"failed to render {var} with rusbie + wrf-rust")
                results.append({"image_path": path, "image_file": os.path.basename(path), "variable": var})
            except Exception as e:
                try:
                    from rustweather import plot
                    fallback_search = var
                    fallback_title = title
                    if var.lower() not in {"stp", "scp", "ehi"}:
                        fallback_search = resolve_image_search(var, model_name)
                        fallback_title = None

                    plot(
                        model=model_name,
                        search=fallback_search,
                        fxx=fhour,
                        date=date_str,
                        area=area,
                        save=path,
                        title=fallback_title,
                    )
                    if os.path.isfile(path):
                        results.append({"image_path": path, "image_file": os.path.basename(path), "variable": var, "renderer": "rustweather-fallback"})
                        continue
                except Exception:
                    pass
                results.append({"variable": var, "error": str(e)})
        return json.dumps({
            "model": model_name.upper(),
            "forecast_hour": fhour,
            "cycle": date_str,
            "images": results,
            "count": len([r for r in results if "image_path" in r]),
        })
    except Exception as e:
        return json.dumps({"error": f"model image failed: {type(e).__name__}: {e}"})


def _run_radar_binary(binary_path: str, args: dict, *, backend: str, storm_cells: bool = False) -> str:
    cmd = [binary_path]

    if args.get("site"):
        cmd.extend(["--site", str(args["site"]).upper()])
    elif args.get("lat") is not None and args.get("lon") is not None:
        cmd.extend(["--lat", str(args["lat"]), "--lon", str(args["lon"])])
    else:
        return json.dumps({"error": "Provide site or lat/lon"})

    if args.get("input"):
        cmd.extend(["--input", str(args["input"])])
    if args.get("product"):
        cmd.extend(["--product", str(args["product"])])

    cmd.extend(["--size", str(args.get("size", 1024))])
    cmd.extend(["--min-dbz", str(args.get("min_dbz", 10))])
    cmd.extend(["--range-km", str(args.get("range_km", 200))])
    if storm_cells:
        cmd.append("--storm-cells")

    out_name = f"radar_{backend}_{args.get('site', 'auto')}_{os.getpid()}.png"
    out_path = str(_IMG_DIR / out_name)
    cmd.extend(["-o", out_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            return json.dumps({"error": err or f"{backend} radar renderer exited {result.returncode}"})
        stdout = result.stdout.strip()
        if not stdout:
            return json.dumps({"error": f"{backend} radar renderer returned no output"})
        data = json.loads(stdout)
        data["backend"] = backend
        data["image_file"] = os.path.basename(data.get("image_path", ""))
        return json.dumps(data)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"{backend} radar renderer timed out (60s)"})
    except FileNotFoundError:
        return json.dumps({"error": f"{backend} radar renderer not found at {binary_path}"})
    except Exception as e:
        return json.dumps({"error": f"radar image failed: {e}"})


def _run_radar_backend(args: dict, *, storm_cells: bool = False) -> str:
    backend = _radar_backend_name()
    binary_path, err = bootstrap.ensure_radar_binary(backend)
    if err:
        return json.dumps({
            "error": err,
            "hint": (
                "Install a Rust toolchain for automatic first-use builds or set RADAR_RENDER_PATH / "
                "NEXRAD_RENDER_PATH to an existing binary."
            ),
        })
    return _run_radar_binary(binary_path, args, backend=backend, storm_cells=storm_cells)


def wx_radar_image(args: dict, **kwargs) -> str:
    return _run_radar_backend(args, storm_cells=False)


def wx_storm_image(args: dict, **kwargs) -> str:
    storm_args = {
        "product": "ref",
        "size": args.get("size", 1024),
        "min_dbz": args.get("min_dbz", 10),
        "range_km": args.get("range_km", 200),
    }
    if args.get("input"):
        storm_args["input"] = args["input"]
    if args.get("site"):
        storm_args["site"] = args["site"]
    elif args.get("lat") is not None and args.get("lon") is not None:
        storm_args["lat"] = args["lat"]
        storm_args["lon"] = args["lon"]
    else:
        return json.dumps({"error": "Provide site or lat/lon"})
    return _run_radar_backend(storm_args, storm_cells=True)
