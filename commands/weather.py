"""
commands/weather.py — Real-time weather via Open-Meteo (free, no key).

Open-Meteo is an open-source weather API with no rate limits for
non-commercial use and no account required.  Docs: https://open-meteo.com

Features
────────
• Current temperature, feels-like, humidity, wind
• Weather condition code → natural English description
• Hourly forecast for "weather today" / "weather tomorrow"
• UV index and precipitation probability
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import requests

from config import WEATHER_LATITUDE, WEATHER_LONGITUDE, WEATHER_UNIT
from utils.logger import setup_logger

logger = setup_logger(__name__)

_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather interpretation codes → human-readable descriptions
_WMO_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "icy fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "light snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "light showers",
    81: "moderate showers",
    82: "violent showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}

_UNIT_SUFFIX = {"celsius": "°C", "fahrenheit": "°F"}


def _fetch_weather(hourly: bool = False) -> Optional[dict]:
    params = {
        "latitude": WEATHER_LATITUDE,
        "longitude": WEATHER_LONGITUDE,
        "current": [
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "weather_code",
            "wind_speed_10m",
            "precipitation_probability",
            "uv_index",
        ],
        "temperature_unit": WEATHER_UNIT,
        "wind_speed_unit": "kmh",
        "timezone": "auto",
    }
    if hourly:
        params["hourly"] = ["temperature_2m", "precipitation_probability", "weather_code"]
        params["forecast_days"] = 2

    try:
        resp = requests.get(_BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.error("Weather API timeout")
        return None
    except Exception as exc:
        logger.error("Weather fetch error: %s", exc)
        return None


def get_current_weather() -> str:
    """Return a spoken-style current weather summary."""
    data = _fetch_weather()
    if not data:
        return "I couldn't fetch the weather right now. Check your internet connection."

    c = data.get("current", {})
    temp      = c.get("temperature_2m")
    feels     = c.get("apparent_temperature")
    humidity  = c.get("relative_humidity_2m")
    wind      = c.get("wind_speed_10m")
    code      = c.get("weather_code", 0)
    precip    = c.get("precipitation_probability", 0)
    uv        = c.get("uv_index", 0)

    condition = _WMO_CODES.get(code, "unknown conditions")
    unit      = _UNIT_SUFFIX.get(WEATHER_UNIT, "°C")

    parts = [
        f"Currently {condition} with a temperature of {temp}{unit}",
        f"feels like {feels}{unit}" if feels else None,
        f"humidity at {humidity}%" if humidity else None,
        f"wind at {wind} km/h" if wind else None,
    ]
    base = ", ".join(p for p in parts if p) + "."

    extras = []
    if precip and precip > 30:
        extras.append(f"There's a {precip}% chance of rain.")
    if uv and uv >= 6:
        extras.append(f"UV index is high at {uv} — sunscreen recommended.")

    return base + (" " + " ".join(extras) if extras else "")


def get_weather_today() -> str:
    """Return a brief today-vs-tomorrow summary."""
    data = _fetch_weather(hourly=True)
    if not data:
        return "Couldn't retrieve the forecast right now."

    hourly = data.get("hourly", {})
    times  = hourly.get("time", [])
    temps  = hourly.get("temperature_2m", [])
    precip = hourly.get("precipitation_probability", [])
    codes  = hourly.get("weather_code", [])

    now  = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    today_temps  = [t for tm, t in zip(times, temps)  if tm.startswith(today_str)]
    today_precip = [p for tm, p in zip(times, precip) if tm.startswith(today_str)]
    today_codes  = [c for tm, c in zip(times, codes)  if tm.startswith(today_str)]

    if not today_temps:
        return get_current_weather()

    unit    = _UNIT_SUFFIX.get(WEATHER_UNIT, "°C")
    hi      = max(today_temps)
    lo      = min(today_temps)
    avg_p   = int(sum(today_precip) / len(today_precip)) if today_precip else 0
    top_c   = max(set(today_codes), key=today_codes.count)
    cond    = _WMO_CODES.get(top_c, "mixed conditions")

    result = f"Today: {cond}, high of {hi}{unit}, low of {lo}{unit}."
    if avg_p > 25:
        result += f" Average rain chance is {avg_p}% — bring an umbrella."
    return result


def get_weather_tomorrow() -> str:
    """Return tomorrow's forecast."""
    data = _fetch_weather(hourly=True)
    if not data:
        return "Couldn't retrieve tomorrow's forecast."

    hourly = data.get("hourly", {})
    times  = hourly.get("time", [])
    temps  = hourly.get("temperature_2m", [])
    precip = hourly.get("precipitation_probability", [])
    codes  = hourly.get("weather_code", [])

    now   = datetime.now()
    day_n = now.toordinal()

    tmr_str = datetime.fromordinal(day_n + 1).strftime("%Y-%m-%d")

    tmr_temps  = [t for tm, t in zip(times, temps)  if tm.startswith(tmr_str)]
    tmr_precip = [p for tm, p in zip(times, precip) if tm.startswith(tmr_str)]
    tmr_codes  = [c for tm, c in zip(times, codes)  if tm.startswith(tmr_str)]

    if not tmr_temps:
        return "Tomorrow's forecast is not available yet."

    unit  = _UNIT_SUFFIX.get(WEATHER_UNIT, "°C")
    hi    = max(tmr_temps)
    lo    = min(tmr_temps)
    avg_p = int(sum(tmr_precip) / len(tmr_precip)) if tmr_precip else 0
    top_c = max(set(tmr_codes), key=tmr_codes.count)
    cond  = _WMO_CODES.get(top_c, "mixed conditions")

    result = f"Tomorrow: {cond}, high of {hi}{unit}, low of {lo}{unit}."
    if avg_p > 25:
        result += f" Rain chance around {avg_p}%."
    return result
