"""Shared model support lists and profile-product hints for Hermes weather tools."""

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


def guess_profile_product(model: str) -> str | None:
    return PROFILE_PRODUCT_HINTS.get((model or "").lower())


def guess_profile_moisture(model: str) -> str:
    return PROFILE_MOISTURE_HINTS.get((model or "").lower(), "dewpoint")
