"""
commands/spotify_ctrl.py — Spotify playback control via spotipy.

Requires free Spotify API credentials:
  1. Go to https://developer.spotify.com/dashboard
  2. Create an app → copy Client ID and Client Secret
  3. Add http://localhost:8888/callback as a redirect URI
  4. Set SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET in config.py
  5. Set SPOTIFY_ENABLED = True in config.py

On first run, a browser window opens for OAuth. After that,
the token is cached in data/.spotify_cache and auth is silent.
"""

from __future__ import annotations

from utils.logger import setup_logger

logger = setup_logger(__name__)


def _get_sp():
    """Return an authenticated Spotipy client, or raise RuntimeError."""
    from config import (
        SPOTIFY_CLIENT_ID,
        SPOTIFY_CLIENT_SECRET,
        SPOTIFY_REDIRECT_URI,
        SPOTIFY_ENABLED,
        DATA_DIR,
    )
    if not SPOTIFY_ENABLED:
        raise RuntimeError(
            "Spotify is disabled. Set SPOTIFY_ENABLED=True and add API keys in config.py"
        )
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise RuntimeError(
            "Spotify credentials missing. Add SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET "
            "to config.py from https://developer.spotify.com/dashboard"
        )

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        raise RuntimeError("spotipy not installed. Run: pip install spotipy")

    scope = " ".join([
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "playlist-read-private",
    ])

    auth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=scope,
        cache_path=str(DATA_DIR / ".spotify_cache"),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth)


def _safe(fn):
    """Decorator: wrap a Spotify call and return a friendly error on failure."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except RuntimeError as exc:
            return str(exc)
        except Exception as exc:
            logger.error("Spotify error: %s", exc)
            return f"Spotify error: {exc}"
    return wrapper


@_safe
def play_pause() -> str:
    sp = _get_sp()
    pb = sp.current_playback()
    if pb and pb.get("is_playing"):
        sp.pause_playback()
        return "Paused Spotify."
    sp.start_playback()
    return "Resumed Spotify."


@_safe
def play_song(query: str) -> str:
    sp = _get_sp()
    results = sp.search(q=query, type="track", limit=1)
    tracks = results.get("tracks", {}).get("items", [])
    if not tracks:
        return f"Couldn't find '{query}' on Spotify."
    track = tracks[0]
    sp.start_playback(uris=[track["uri"]])
    artist = track["artists"][0]["name"]
    name   = track["name"]
    return f"Playing {name} by {artist}."


@_safe
def skip_next() -> str:
    _get_sp().next_track()
    return "Skipped to the next track."


@_safe
def skip_prev() -> str:
    _get_sp().previous_track()
    return "Going back to the previous track."


@_safe
def set_volume_spotify(level: int) -> str:
    level = max(0, min(100, level))
    _get_sp().volume(level)
    return f"Spotify volume set to {level}%."


@_safe
def now_playing() -> str:
    sp = _get_sp()
    track = sp.current_user_playing_track()
    if not track or not track.get("item"):
        return "Nothing is playing on Spotify right now."
    item   = track["item"]
    name   = item["name"]
    artist = item["artists"][0]["name"]
    album  = item["album"]["name"]
    return f"Currently playing: {name} by {artist} from the album {album}."
