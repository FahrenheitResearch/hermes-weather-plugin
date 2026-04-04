"""Shared model support lists, field aliases, and product hints for Hermes weather tools."""

IMAGE_MODELS = [
    "aigfs",
    "gdas",
    "gefs",
    "gfs",
    "graphcast",
    "hiresw",
    "hrrr",
    "hrrrak",
    "nam",
    "nbm",
    "rap",
]

PROFILE_MODELS = [
    "gdas",
    "gfs",
    "graphcast",
    "hrrr",
    "hrrrak",
    "rrfs",
]

MODEL_DESCRIPTIONS = {
    "aifs": "ECMWF AIFS ML Global",
    "aigefs": "AI-GEFS Ensemble",
    "aigfs": "AI-GFS Global",
    "cfs": "CFS Seasonal Forecast",
    "gdas": "GDAS 0.25deg",
    "gdps": "GDPS Global",
    "gefs": "GEFS Ensemble 0.5deg",
    "gfs": "GFS 0.25deg Global",
    "gfs_wave": "GFS Wave Model",
    "graphcast": "GraphCast ML Global",
    "hgefs": "High-Res GEFS Ensemble",
    "hrdps": "HRDPS High-Resolution",
    "hiresw": "HiResW 5km CONUS",
    "href": "HREF Ensemble Mean",
    "hrrr": "HRRR 3km CONUS",
    "hrrrak": "HRRR-Alaska 3km",
    "ifs": "ECMWF IFS Global",
    "nam": "NAM 12km CONUS",
    "navgem_nomads": "NAVGEM via NOMADS",
    "nbm": "National Blend of Models CONUS",
    "nbmqmd": "NBM Quantile-Mapped",
    "rap": "RAP 13km CONUS",
    "rap_historical": "RAP Historical Archive",
    "rap_ncei": "RAP NCEI Archive",
    "rdps": "RDPS Regional",
    "rrfs": "RRFS 3km CONUS",
    "rtma": "RTMA CONUS Analysis",
    "rtma_ak": "RTMA Alaska",
    "rtma_ru": "RTMA Rapid Update",
    "urma": "URMA CONUS Analysis",
    "urma_ak": "URMA Alaska",
}

PROFILE_PRODUCT_HINTS = {
    "gdas": "pgrb2.0p25",
    "gfs": "pgrb2.0p25",
    "graphcast": "pgrb2.0p25",
    "hrrr": "prs",
    "hrrrak": "prs",
    "nam": "awphys",
    "rrfs": "prslev",
}

PROFILE_MOISTURE_HINTS = {
    "gdas": "specific_humidity",
    "gfs": "specific_humidity",
    "graphcast": "specific_humidity",
    "hrrr": "dewpoint",
    "hrrrak": "dewpoint",
    "nam": "relative_humidity",
    "rrfs": "dewpoint",
}

IMAGE_FIELD_ALIASES = {
    "temp": "TMP:2 m above ground",
    "temperature": "TMP:2 m above ground",
    "t2m": "TMP:2 m above ground",
    "dewpoint": "DPT:2 m above ground",
    "td": "DPT:2 m above ground",
    "td2m": "DPT:2 m above ground",
    "wind": "UGRD:10 m above ground|VGRD:10 m above ground",
    "u10": "UGRD:10 m above ground",
    "v10": "VGRD:10 m above ground",
    "gust": "GUST:surface",
    "pressure": "PRMSL:mean sea level",
    "mslp": "PRMSL:mean sea level",
    "cape": "CAPE:surface",
    "cin": "CIN:surface",
    "mlcape": "CAPE:90-0 mb above ground",
    "mlcin": "CIN:90-0 mb above ground",
    "mucape": "CAPE:255-0 mb above ground",
    "sbcape": "CAPE:surface",
    "sbcin": "CIN:surface",
    "reflectivity": "REFC:entire atmosphere",
    "refl": "REFC:entire atmosphere",
    "composite_reflectivity": "REFC:entire atmosphere",
    "precip": "APCP:surface",
    "precipitation": "APCP:surface",
    "snow": "WEASD:surface",
    "pwat": "PWAT:entire atmosphere",
    "precipitable_water": "PWAT:entire atmosphere",
    "rh": "RH:2 m above ground",
    "relative_humidity": "RH:2 m above ground",
    "visibility": "VIS:surface",
    "vis": "VIS:surface",
    "srh": "HLCY:3000-0 m above ground",
    "srh03": "HLCY:3000-0 m above ground",
    "srh01": "HLCY:1000-0 m above ground",
    "helicity": "HLCY:3000-0 m above ground",
    "updraft_helicity": "MXUPHL:5000-2000 m above ground",
    "uh": "MXUPHL:5000-2000 m above ground",
    "heights_500": "HGT:500 mb",
    "heights_250": "HGT:250 mb",
    "heights_850": "HGT:850 mb",
    "heights_700": "HGT:700 mb",
    "vorticity_500": "ABSV:500 mb",
    "jet": "UGRD:250 mb|VGRD:250 mb",
    "wind_250": "UGRD:250 mb|VGRD:250 mb",
    "wind_850": "UGRD:850 mb|VGRD:850 mb",
    "temp_850": "TMP:850 mb",
    "temp_700": "TMP:700 mb",
    "rh_700": "RH:700 mb",
    "cloud": "TCDC:entire atmosphere",
    "cloud_cover": "TCDC:entire atmosphere",
    "bulk_shear": "VUCSH:0-6000 m above ground|VVCSH:0-6000 m above ground",
    "shear_0_6km": "VUCSH:0-6000 m above ground|VVCSH:0-6000 m above ground",
    "shear_0_1km": "VUCSH:0-1000 m above ground|VVCSH:0-1000 m above ground",
    "cape3d": "CAPE:3000-0 m above ground",
}

IFS_IMAGE_FIELD_ALIASES = {
    "temp": ":2t:sfc:",
    "temperature": ":2t:sfc:",
    "t2m": ":2t:sfc:",
    "dewpoint": ":2d:sfc:",
    "td": ":2d:sfc:",
    "wind": ":10u:sfc:|:10v:sfc:",
    "u10": ":10u:sfc:",
    "v10": ":10v:sfc:",
    "pressure": ":sp:sfc:",
    "mslp": ":msl:sfc:",
    "cape": ":cape:sfc:",
    "precip": ":tp:sfc:",
    "cloud_cover": ":tcc:sfc:",
    "cloud": ":tcc:sfc:",
    "pwat": ":tcwv:sfc:",
    "heights_500": ":z:500:pl:",
    "temp_850": ":t:850:pl:",
    "temp_500": ":t:500:pl:",
    "wind_850": ":u:850:pl:|:v:850:pl:",
    "jet": ":u:250:pl:|:v:250:pl:",
    "vorticity_500": ":vo:500:pl:",
}


def guess_profile_product(model: str) -> str | None:
    return PROFILE_PRODUCT_HINTS.get((model or "").lower())


def guess_profile_moisture(model: str) -> str:
    return PROFILE_MOISTURE_HINTS.get((model or "").lower(), "dewpoint")


def resolve_image_search(search: str, model: str | None = None) -> str:
    if ":" in search:
        return search
    key = search.strip().lower().replace(" ", "_").replace("-", "_")
    if model and model.lower() in ("ifs", "aifs", "ecmwf") and key in IFS_IMAGE_FIELD_ALIASES:
        return IFS_IMAGE_FIELD_ALIASES[key]
    if key in IMAGE_FIELD_ALIASES:
        return IMAGE_FIELD_ALIASES[key]
    raise KeyError(
        f"Unknown image field alias {search!r}. Use a GRIB search string or one of: "
        f"{', '.join(sorted(IMAGE_FIELD_ALIASES))}"
    )
