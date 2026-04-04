"""Tier 3 — Calculation tool handlers. metrust-py in-process, Rust-backed."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from .. import bootstrap
from ..model_support import PROFILE_MODELS, guess_profile_moisture, guess_profile_product

logger = logging.getLogger(__name__)


def _find_ecape_runner() -> str | None:
    runner, _ = bootstrap.ensure_ecape_runner()
    return runner


def _load_model_profile(args: dict):
    from rusbie import HerbieLatest
    from metrust import calc as mcalc
    import numpy as np

    lat, lon = args.get("lat"), args.get("lon")
    if lat is None or lon is None:
        raise ValueError("lat and lon are required")

    model = args.get("model", "hrrr")
    if model not in PROFILE_MODELS:
        raise ValueError(f"Model {model!r} is not currently enabled for profile-based tools. Supported: {PROFILE_MODELS}")
    product = guess_profile_product(model)
    H = HerbieLatest(model=model, fxx=0, n=1, product=product)
    cycle = str(H.date)

    ds_tmp = H.xarray(":TMP:.*mb:", verbose=False, remove_grib=False)
    dewpoint_mode = guess_profile_moisture(model)
    moisture_search = {
        "dewpoint": ":DPT:.*mb:",
        "specific_humidity": ":SPFH:.*mb:",
        "relative_humidity": ":RH:.*mb:",
    }[dewpoint_mode]
    ds_moist = H.xarray(moisture_search, verbose=False, remove_grib=False)
    ds_u = H.xarray(":UGRD:.*mb:", verbose=False, remove_grib=False)
    ds_v = H.xarray(":VGRD:.*mb:", verbose=False, remove_grib=False)
    ds_hgt = H.xarray(":HGT:.*mb:", verbose=False, remove_grib=False)

    def _nearest(ds, lat, lon):
        if "latitude" not in ds.coords or "longitude" not in ds.coords:
            raise ValueError(
                f"Model {model!r} profile extraction requires latitude/longitude coordinates; available coords are {list(ds.coords)}"
            )
        lat_arr = ds.latitude.values
        lon_arr = ds.longitude.values
        if lat_arr.ndim == 1:
            j = np.argmin(np.abs(lat_arr - lat))
            i = np.argmin(np.abs(lon_arr - lon))
            vname = list(ds.data_vars)[0]
            vals = ds[vname].values
            while vals.ndim > 1:
                if vals.shape[-2] > 1 and vals.shape[-1] > 1:
                    return vals[:, j, i] if vals.ndim == 3 else vals[j, i]
                vals = vals.squeeze()
            return vals
        lon_g = lon_arr
        if lon_g.max() > 180:
            lon_g = np.where(lon_g > 180, lon_g - 360, lon_g)
        dist = (lat_arr - lat) ** 2 + (lon_g - lon) ** 2
        j, i = np.unravel_index(dist.argmin(), dist.shape)
        vname = list(ds.data_vars)[0]
        vals = ds[vname].values
        if vals.ndim == 3:
            return vals[:, j, i]
        if vals.ndim == 2:
            return vals[j, i]
        return vals

    pres_coord = None
    pres_scale = 1.0
    for coord in ds_tmp.coords:
        vals = ds_tmp[coord].values
        if vals.ndim == 1 and len(vals) > 3:
            if 100 < vals.max() < 1100:
                pres_coord = coord
                pres_scale = 1.0
                break
            if vals.max() > 50000:
                pres_coord = coord
                pres_scale = 0.01
                break

    if pres_coord is None:
        raise ValueError("Could not identify pressure levels")

    pressure = ds_tmp[pres_coord].values * pres_scale
    temp_k = _nearest(ds_tmp, lat, lon)
    moist = _nearest(ds_moist, lat, lon)
    u_ms = _nearest(ds_u, lat, lon)
    v_ms = _nearest(ds_v, lat, lon)
    hgt_m = _nearest(ds_hgt, lat, lon)

    sort_idx = np.argsort(pressure)[::-1]
    pressure = pressure[sort_idx]
    temp_k = temp_k[sort_idx]
    moist = moist[sort_idx]
    u_ms = u_ms[sort_idx]
    v_ms = v_ms[sort_idx]
    hgt_m = hgt_m[sort_idx]

    if dewpoint_mode == "dewpoint":
        dewp_k = moist
    elif dewpoint_mode == "specific_humidity":
        dewp_c = np.asarray(
            [float(mcalc.dewpoint_from_specific_humidity(float(p), float(q)).magnitude) for p, q in zip(pressure, moist)],
            dtype=float,
        )
        dewp_k = dewp_c + 273.15
    else:
        temp_c = temp_k - 273.15
        dewp_c = np.asarray(
            [float(mcalc.dewpoint_from_relative_humidity(float(t), float(rh)).magnitude) for t, rh in zip(temp_c, moist)],
            dtype=float,
        )
        dewp_k = dewp_c + 273.15

    return {
        "lat": lat,
        "lon": lon,
        "model": model,
        "cycle": cycle,
        "pressure_hpa": pressure.tolist(),
        "height_m": hgt_m.tolist(),
        "temperature_k": temp_k.tolist(),
        "dewpoint_k": dewp_k.tolist(),
        "u_ms": u_ms.tolist(),
        "v_ms": v_ms.tolist(),
    }


def wx_calc(args: dict, **kwargs) -> str:
    func_name = args.get("function")
    if not func_name:
        return json.dumps({"error": "function name is required"})

    try:
        from metrust import calc
        from metrust.units import units as ureg
    except ImportError:
        return json.dumps({"error": "metrust not installed"})

    func = getattr(calc, func_name, None)
    if func is None:
        return json.dumps({
            "error": f"Unknown function: {func_name}",
            "hint": "Use a metrust.calc function name like 'dewpoint_from_relative_humidity', 'wind_speed', 'lcl', etc.",
        })

    func_args = args.get("args", {})
    if not isinstance(func_args, dict):
        return json.dumps({"error": "args must be a JSON object"})

    try:
        import numpy as np
        parsed = {}
        for key, val in func_args.items():
            if isinstance(val, str) and any(c.isalpha() for c in val):
                parsed[key] = ureg.Quantity(val)
            elif isinstance(val, list):
                parsed[key] = np.array(val)
            else:
                parsed[key] = val

        result = func(**parsed)

        if hasattr(result, "magnitude"):
            mag = result.magnitude
            if hasattr(mag, "ndim"):
                val = float(mag) if mag.ndim == 0 else mag.tolist()
            else:
                val = float(mag)
            return json.dumps({
                "function": func_name,
                "result": val,
                "units": str(result.units),
            })
        elif hasattr(result, "__len__") and not isinstance(result, str):
            formatted = []
            for r in result:
                if hasattr(r, "magnitude"):
                    mag = r.magnitude
                    if hasattr(mag, "ndim"):
                        v = float(mag) if mag.ndim == 0 else mag.tolist()
                    else:
                        v = float(mag)
                    formatted.append({"value": v, "units": str(r.units)})
                else:
                    formatted.append({"value": r})
            return json.dumps({"function": func_name, "results": formatted})
        else:
            return json.dumps({"function": func_name, "result": str(result)})

    except Exception as e:
        return json.dumps({
            "function": func_name,
            "error": f"{type(e).__name__}: {e}",
        })


def wx_sounding(args: dict, **kwargs) -> str:
    lat, lon = args.get("lat"), args.get("lon")
    if lat is None or lon is None:
        return json.dumps({"error": "lat and lon are required"})

    try:
        from metrust import calc
        from metrust.units import units as ureg
        import numpy as np

        profile_data = _load_model_profile(args)
        model = profile_data["model"]
        cycle = profile_data["cycle"]
        pressure = np.asarray(profile_data["pressure_hpa"], dtype=float)
        temp_k = np.asarray(profile_data["temperature_k"], dtype=float)
        dewp_k = np.asarray(profile_data["dewpoint_k"], dtype=float)
        u_ms = np.asarray(profile_data["u_ms"], dtype=float)
        v_ms = np.asarray(profile_data["v_ms"], dtype=float)
        hgt_m = np.asarray(profile_data["height_m"], dtype=float)

        temp_c = temp_k - 273.15
        dewp_c = dewp_k - 273.15
        wspd_kt = np.sqrt(u_ms**2 + v_ms**2) * 1.94384
        wdir_deg = (270 - np.degrees(np.arctan2(v_ms, u_ms))) % 360

        p_q = ureg.Quantity(pressure, "hPa")
        t_q = ureg.Quantity(temp_c, "degC")
        td_q = ureg.Quantity(dewp_c, "degC")
        u_q = ureg.Quantity(u_ms, "m/s")
        v_q = ureg.Quantity(v_ms, "m/s")
        h_q = ureg.Quantity(hgt_m, "m")

        params = {}
        params["sfc_pressure_hpa"] = round(float(pressure[0]), 1)
        params["sfc_temp_c"] = round(float(temp_c[0]), 1)
        params["sfc_temp_f"] = round(float(temp_c[0]) * 9/5 + 32, 1)
        params["sfc_dewpoint_c"] = round(float(dewp_c[0]), 1)
        params["sfc_dewpoint_f"] = round(float(dewp_c[0]) * 9/5 + 32, 1)
        params["sfc_wind_kt"] = round(float(wspd_kt[0]), 1)
        params["sfc_wind_dir"] = round(float(wdir_deg[0]))

        try:
            lcl_p, lcl_t = calc.lcl(p_q[0], t_q[0], td_q[0])
            params["lcl_pressure_hpa"] = round(float(lcl_p.magnitude), 1)
            params["lcl_temp_c"] = round(float(lcl_t.magnitude), 1)
            lcl_hgt_idx = np.argmin(np.abs(pressure - float(lcl_p.magnitude)))
            params["lcl_height_m_agl"] = round(float(hgt_m[lcl_hgt_idx] - hgt_m[0]))
        except Exception:
            pass

        try:
            lfc_p, lfc_t = calc.lfc(p_q, t_q, td_q)
            params["lfc_pressure_hpa"] = round(float(lfc_p.magnitude), 1)
        except Exception:
            pass

        try:
            el_p, el_t = calc.el(p_q, t_q, td_q)
            params["el_pressure_hpa"] = round(float(el_p.magnitude), 1)
        except Exception:
            pass

        try:
            cape, cin = calc.surface_based_cape_cin(p_q, t_q, td_q)
            params["sbcape_jkg"] = round(float(cape.magnitude), 1)
            params["sbcin_jkg"] = round(float(cin.magnitude), 1)
        except Exception:
            pass

        try:
            mlcape, mlcin = calc.mixed_layer_cape_cin(p_q, t_q, td_q)
            params["mlcape_jkg"] = round(float(mlcape.magnitude), 1)
            params["mlcin_jkg"] = round(float(mlcin.magnitude), 1)
        except Exception:
            pass

        try:
            mucape, mucin = calc.most_unstable_cape_cin(p_q, t_q, td_q)
            params["mucape_jkg"] = round(float(mucape.magnitude), 1)
            params["mucin_jkg"] = round(float(mucin.magnitude), 1)
        except Exception:
            pass

        try:
            li = calc.lifted_index(p_q, t_q, td_q)
            params["lifted_index"] = round(float(li.magnitude), 1)
        except Exception:
            pass

        try:
            ki = calc.k_index(p_q, t_q, td_q)
            params["k_index"] = round(float(ki.magnitude), 1)
        except Exception:
            pass

        try:
            tt = calc.total_totals(p_q, t_q, td_q)
            params["total_totals"] = round(float(tt.magnitude), 1)
        except Exception:
            pass

        try:
            bs = calc.bulk_shear(p_q, u_q, v_q, height=h_q, depth=ureg.Quantity(6000, "m"))
            bs_mag = float(np.sqrt(bs[0].magnitude**2 + bs[1].magnitude**2))
            params["bulk_shear_0_6km_kt"] = round(bs_mag * 1.94384, 1)
        except Exception:
            pass

        try:
            bs1 = calc.bulk_shear(p_q, u_q, v_q, height=h_q, depth=ureg.Quantity(1000, "m"))
            bs1_mag = float(np.sqrt(bs1[0].magnitude**2 + bs1[1].magnitude**2))
            params["bulk_shear_0_1km_kt"] = round(bs1_mag * 1.94384, 1)
        except Exception:
            pass

        try:
            srh3 = calc.storm_relative_helicity(p_q, u_q, v_q, h_q, depth=ureg.Quantity(3000, "m"))
            if hasattr(srh3, '__len__') and len(srh3) >= 3:
                params["srh_0_3km"] = round(float(srh3[2].magnitude), 1)
            else:
                params["srh_0_3km"] = round(float(srh3.magnitude), 1)
        except Exception:
            pass

        try:
            srh1 = calc.storm_relative_helicity(p_q, u_q, v_q, h_q, depth=ureg.Quantity(1000, "m"))
            if hasattr(srh1, '__len__') and len(srh1) >= 3:
                params["srh_0_1km"] = round(float(srh1[2].magnitude), 1)
            else:
                params["srh_0_1km"] = round(float(srh1.magnitude), 1)
        except Exception:
            pass

        try:
            pw = calc.precipitable_water(p_q, td_q)
            params["precipitable_water_mm"] = round(float(pw.magnitude), 1)
        except Exception:
            pass

        try:
            rm, lm, mean = calc.bunkers_storm_motion(p_q, u_q, v_q, h_q)
            rm_spd = float(np.sqrt(rm[0].magnitude**2 + rm[1].magnitude**2)) * 1.94384
            params["bunkers_rm_kt"] = round(rm_spd, 1)
        except Exception:
            pass

        try:
            stp = calc.significant_tornado(
                ureg.Quantity(params.get("sbcape_jkg", 0), "J/kg"),
                ureg.Quantity(params.get("lcl_height_m_agl", 2000), "m"),
                ureg.Quantity(params.get("srh_0_1km", 0), "m^2/s^2"),
                ureg.Quantity(params.get("bulk_shear_0_6km_kt", 0) / 1.94384, "m/s"),
            )
            params["stp_fixed"] = round(float(stp.magnitude), 2)
        except Exception:
            pass

        try:
            sfc_idx = 0
            idx_3km = np.argmin(np.abs(hgt_m - (hgt_m[0] + 3000)))
            if idx_3km > sfc_idx:
                lr_03 = -(temp_c[idx_3km] - temp_c[sfc_idx]) / ((hgt_m[idx_3km] - hgt_m[sfc_idx]) / 1000)
                params["lapse_rate_0_3km_c_km"] = round(float(lr_03), 1)
            idx_700 = np.argmin(np.abs(pressure - 700))
            idx_500 = np.argmin(np.abs(pressure - 500))
            if idx_700 != idx_500:
                lr_75 = -(temp_c[idx_500] - temp_c[idx_700]) / ((hgt_m[idx_500] - hgt_m[idx_700]) / 1000)
                params["lapse_rate_700_500_c_km"] = round(float(lr_75), 1)
        except Exception:
            pass

        try:
            freeze_idx = np.where(temp_c <= 0)[0]
            if len(freeze_idx) > 0:
                params["freezing_level_m_agl"] = round(float(hgt_m[freeze_idx[0]] - hgt_m[0]))
        except Exception:
            pass

        profile = []
        for p_level in [1000, 925, 850, 700, 500, 300, 250]:
            idx = np.argmin(np.abs(pressure - p_level))
            if abs(pressure[idx] - p_level) < 25:
                profile.append({
                    "pressure_hpa": round(float(pressure[idx])),
                    "height_m": round(float(hgt_m[idx])),
                    "temp_c": round(float(temp_c[idx]), 1),
                    "dewpoint_c": round(float(dewp_c[idx]), 1),
                    "wind_dir": round(float(wdir_deg[idx])),
                    "wind_kt": round(float(wspd_kt[idx]), 1),
                })

        return json.dumps({
            "location": {"lat": lat, "lon": lon},
            "model": model,
            "cycle": cycle,
            "parameters": params,
            "profile": profile,
            "levels_available": len(pressure),
        })

    except ImportError as e:
        return json.dumps({"error": f"Missing package: {e}"})
    except Exception as e:
        return json.dumps({"error": f"sounding failed: {type(e).__name__}: {e}"})

def wx_ecape(args: dict, **kwargs) -> str:
    lat, lon = args.get("lat"), args.get("lon")
    if lat is None or lon is None:
        return json.dumps({"error": "lat and lon are required"})

    runner = _find_ecape_runner()
    if not runner:
        return json.dumps({
            "error": "ecape-rs runner not found",
            "hint": "Install a Rust toolchain for automatic first-use builds or set ECAPE_RS_RUNNER to an existing run_case binary.",
        })

    try:
        profile_data = _load_model_profile(args)
        include_profile = bool(args.get("include_parcel_profile", False))
        payload = {
            "pressure_hpa": profile_data["pressure_hpa"],
            "height_m": profile_data["height_m"],
            "temperature_k": profile_data["temperature_k"],
            "dewpoint_k": profile_data["dewpoint_k"],
            "u_wind_ms": profile_data["u_ms"],
            "v_wind_ms": profile_data["v_ms"],
            "options": {
                "cape_type": args.get("cape_type", "most_unstable"),
                "storm_motion_type": args.get("storm_motion_type", "right_moving"),
                "storm_motion_u_ms": args.get("storm_motion_u_ms"),
                "storm_motion_v_ms": args.get("storm_motion_v_ms"),
                "pseudoadiabatic": args.get("pseudoadiabatic", True),
            },
            "reps": 1,
        }
        proc = subprocess.run(
            [runner],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
        )
        out = json.loads(proc.stdout)
        result = {
            "location": {"lat": lat, "lon": lon},
            "model": profile_data["model"],
            "cycle": profile_data["cycle"],
            "mode": {
                "cape_type": payload["options"]["cape_type"],
                "storm_motion_type": payload["options"]["storm_motion_type"],
                "pseudoadiabatic": payload["options"]["pseudoadiabatic"],
            },
            "metrics": {
                "ecape_jkg": out["ecape_jkg"],
                "ncape_jkg": out["ncape_jkg"],
                "cape_jkg": out["cape_jkg"],
                "cin_jkg": out["cin_jkg"],
                "lfc_m": out["lfc_m"],
                "el_m": out["el_m"],
                "storm_motion_u_ms": out["storm_motion_u_ms"],
                "storm_motion_v_ms": out["storm_motion_v_ms"],
            },
            "runner": {
                "path": runner,
                "per_call_ms": out["per_call_ms"],
            },
        }
        if include_profile:
            result["parcel_profile"] = {
                "pressure_pa": out["parcel_pressure_pa"],
                "height_m": out["parcel_height_m"],
                "temperature_k": out["parcel_temperature_k"],
                "qv_kgkg": out["parcel_qv_kgkg"],
                "qt_kgkg": out["parcel_qt_kgkg"],
            }
        return json.dumps(result)
    except subprocess.CalledProcessError as e:
        return json.dumps({
            "error": "ecape-rs runner failed",
            "stderr": e.stderr.strip(),
        })
    except Exception as e:
        return json.dumps({"error": f"ecape failed: {type(e).__name__}: {e}"})



