from __future__ import annotations

from typing import Any, Dict

import requests

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TIMEOUT_SECONDS = 15


def _safe_get(source: Dict[str, Any], key: str, default: Any = None) -> Any:
    value = source.get(key, default)
    return default if value is None else value


def fetch_weather_snapshot(lat: float, lon: float) -> Dict[str, Any]:
    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "current": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "is_day",
            "cloud_cover",
            "precipitation",
            "weather_code",
            "uv_index",
            "wind_speed_10m",
        ]),
    }
    weather_response = requests.get(WEATHER_URL, params=weather_params, timeout=TIMEOUT_SECONDS)
    weather_response.raise_for_status()
    weather_json = weather_response.json()
    current = weather_json.get("current", {})

    air_params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "current": "european_aqi,us_aqi,pm2_5,pm10,uv_index",
    }
    # AQI is optional: its outage must not discard a successful weather lookup.
    try:
        air_response = requests.get(AIR_QUALITY_URL, params=air_params, timeout=TIMEOUT_SECONDS)
        air_response.raise_for_status()
        air_json = air_response.json()
        air_current = air_json.get("current", {})
    except (requests.RequestException, ValueError):
        air_current = {}

    uv = _safe_get(current, "uv_index", _safe_get(air_current, "uv_index", 0))

    return {
        "source": "open-meteo",
        "latitude": lat,
        "longitude": lon,
        "time": current.get("time"),
        "temperature_c": _safe_get(current, "temperature_2m", 0),
        "feels_like_c": _safe_get(current, "apparent_temperature", 0),
        "is_day": bool(_safe_get(current, "is_day", 1)),
        "cloud_cover": _safe_get(current, "cloud_cover", 0),
        "precipitation": _safe_get(current, "precipitation", 0),
        "weather_code": _safe_get(current, "weather_code", -1),
        "wind_speed_kmh": _safe_get(current, "wind_speed_10m", 0),
        "uv_index": uv,
        "aqi_eu": _safe_get(air_current, "european_aqi", None),
        "aqi_us": _safe_get(air_current, "us_aqi", None),
        "pm2_5": _safe_get(air_current, "pm2_5", None),
        "pm10": _safe_get(air_current, "pm10", None),
    }
