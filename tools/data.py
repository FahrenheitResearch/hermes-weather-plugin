"""Tier 1 — Data tool handlers. Pure Python, hit NWS/METAR/SPC APIs directly."""

import json
from .. import nws


def wx_conditions(args: dict, **kwargs) -> str:
    lat, lon = args.get("lat"), args.get("lon")
    if lat is None or lon is None:
        return json.dumps({"error": "lat and lon are required"})
    return nws.get_conditions(lat, lon)


def wx_forecast(args: dict, **kwargs) -> str:
    lat, lon = args.get("lat"), args.get("lon")
    if lat is None or lon is None:
        return json.dumps({"error": "lat and lon are required"})
    return nws.get_forecast(lat, lon, hourly=bool(args.get("hourly")))


def wx_alerts(args: dict, **kwargs) -> str:
    if args.get("state"):
        return nws.get_alerts(state=args["state"])
    elif args.get("lat") is not None and args.get("lon") is not None:
        return nws.get_alerts(lat=args["lat"], lon=args["lon"])
    return json.dumps({"error": "Provide lat/lon or state"})


def wx_metar(args: dict, **kwargs) -> str:
    station = args.get("station")
    if not station:
        return json.dumps({"error": "station is required"})
    return nws.get_metar(station)


def wx_brief(args: dict, **kwargs) -> str:
    lat, lon = args.get("lat"), args.get("lon")
    if lat is None or lon is None:
        return json.dumps({"error": "lat and lon are required"})
    try:
        conditions = json.loads(nws.get_conditions(lat, lon))
        forecast = json.loads(nws.get_forecast(lat, lon))
        alerts = json.loads(nws.get_alerts(lat=lat, lon=lon))
        return json.dumps({
            "conditions": conditions,
            "forecast_periods": forecast.get("periods", [])[:3],
            "alert_count": alerts.get("count", 0),
            "alerts_summary": [a.get("headline") for a in alerts.get("alerts", [])[:3]],
        })
    except Exception as e:
        return json.dumps({"error": f"brief failed: {e}"})


def wx_global(args: dict, **kwargs) -> str:
    lat, lon = args.get("lat"), args.get("lon")
    if lat is None or lon is None:
        return json.dumps({"error": "lat and lon are required"})
    return nws.get_global(lat, lon)


def wx_severe(args: dict, **kwargs) -> str:
    if args.get("state"):
        return nws.get_severe(state=args["state"])
    elif args.get("lat") is not None and args.get("lon") is not None:
        return nws.get_severe(lat=args["lat"], lon=args["lon"])
    return json.dumps({"error": "Provide lat/lon or state"})
