"""
commands/home_auto.py — Home Assistant integration for smart-home control.

Talks to a local Home Assistant instance via its REST API.
No cloud needed — works entirely over your LAN.

Setup
─────
1. In Home Assistant → Profile → Long-Lived Access Tokens → Create Token
2. Set HA_BASE_URL and HA_TOKEN in config.py
3. Set HA_ENABLED = True

Usage
─────
  "turn on the bedroom light"
  "turn off the living room fan"
  "set the thermostat to 22"
"""

from __future__ import annotations

from utils.logger import setup_logger

logger = setup_logger(__name__)


def _get_config():
    from config import (
        HA_ENABLED,
        HA_BASE_URL,
        HA_TOKEN,
    )
    if not HA_ENABLED:
        raise RuntimeError(
            "Home Assistant is disabled. Set HA_ENABLED=True and add "
            "HA_BASE_URL / HA_TOKEN in config.py"
        )
    return HA_BASE_URL, HA_TOKEN


def _ha_request(method: str, path: str, json_data: dict | None = None) -> dict:
    """Make an authenticated request to Home Assistant."""
    import requests

    base_url, token = _get_config()
    url = f"{base_url}/api/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.request(method, url, headers=headers, json=json_data, timeout=10)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


# ── Entity ID resolution ─────────────────────────────────────────────────────

# Map spoken names → Home Assistant entity IDs
# Users should customise this for their setup
_ENTITY_MAP: dict[str, str] = {
    "bedroom light":     "light.bedroom",
    "living room light": "light.living_room",
    "kitchen light":     "light.kitchen",
    "office light":      "light.office",
    "hallway light":     "light.hallway",
    "bathroom light":    "light.bathroom",
    "fan":               "fan.living_room",
    "living room fan":   "fan.living_room",
    "bedroom fan":       "fan.bedroom",
    "thermostat":        "climate.thermostat",
    "ac":                "climate.thermostat",
    "air conditioner":   "climate.thermostat",
    "tv":                "media_player.tv",
    "television":        "media_player.tv",
}


def _resolve_entity(name: str) -> str | None:
    """Resolve a spoken device name to a Home Assistant entity_id."""
    name = name.lower().strip()
    # Direct match
    if name in _ENTITY_MAP:
        return _ENTITY_MAP[name]
    # Partial match
    for spoken, entity_id in _ENTITY_MAP.items():
        if name in spoken or spoken in name:
            return entity_id
    return None


# ── Public command handlers ──────────────────────────────────────────────────

def turn_on(device_name: str) -> str:
    """Turn on a smart device."""
    try:
        entity_id = _resolve_entity(device_name)
        if not entity_id:
            return f"I don't recognise the device '{device_name}'. You can add it to commands/home_auto.py."
        domain = entity_id.split(".")[0]
        _ha_request("POST", "services/{}/turn_on".format(domain), {"entity_id": entity_id})
        logger.info("HA: turned on %s (%s)", device_name, entity_id)
        return f"Turned on the {device_name}."
    except RuntimeError as exc:
        return str(exc)
    except Exception as exc:
        logger.error("HA turn_on error: %s", exc)
        return f"Couldn't turn on the {device_name}: {exc}"


def turn_off(device_name: str) -> str:
    """Turn off a smart device."""
    try:
        entity_id = _resolve_entity(device_name)
        if not entity_id:
            return f"I don't recognise the device '{device_name}'. You can add it to commands/home_auto.py."
        domain = entity_id.split(".")[0]
        _ha_request("POST", "services/{}/turn_off".format(domain), {"entity_id": entity_id})
        logger.info("HA: turned off %s (%s)", device_name, entity_id)
        return f"Turned off the {device_name}."
    except RuntimeError as exc:
        return str(exc)
    except Exception as exc:
        logger.error("HA turn_off error: %s", exc)
        return f"Couldn't turn off the {device_name}: {exc}"


def set_temperature(temp: int) -> str:
    """Set the thermostat temperature."""
    try:
        entity_id = _resolve_entity("thermostat")
        if not entity_id:
            return "No thermostat configured in the entity map."
        _ha_request("POST", "services/climate/set_temperature", {
            "entity_id": entity_id,
            "temperature": temp,
        })
        logger.info("HA: thermostat set to %d", temp)
        return f"Thermostat set to {temp} degrees."
    except RuntimeError as exc:
        return str(exc)
    except Exception as exc:
        logger.error("HA set_temperature error: %s", exc)
        return f"Couldn't set the temperature: {exc}"


def get_device_state(device_name: str) -> str:
    """Query the state of a smart device."""
    try:
        entity_id = _resolve_entity(device_name)
        if not entity_id:
            return f"I don't recognise '{device_name}'."
        data = _ha_request("GET", f"states/{entity_id}")
        state = data.get("state", "unknown")
        friendly = data.get("attributes", {}).get("friendly_name", device_name)
        return f"The {friendly} is currently {state}."
    except RuntimeError as exc:
        return str(exc)
    except Exception as exc:
        logger.error("HA state query error: %s", exc)
        return f"Couldn't check {device_name}: {exc}"
