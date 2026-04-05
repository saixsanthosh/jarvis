"""
commands/news_cmd.py — News briefing via RSS feeds (no API key).
"""
from __future__ import annotations
import xml.etree.ElementTree as ET
import requests
from utils.logger import setup_logger

logger = setup_logger(__name__)

_FEEDS = {
    "tech":    "https://feeds.arstechnica.com/arstechnica/index",
    "world":   "http://feeds.bbci.co.uk/news/world/rss.xml",
    "science": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "india":   "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "general": "http://feeds.bbci.co.uk/news/rss.xml",
}

def _parse_rss(url: str, limit: int = 5) -> list[str]:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Jarvis/2.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:limit]
        return [item.findtext("title", "").strip() for item in items if item.findtext("title")]
    except Exception as exc:
        logger.error("RSS fetch error: %s", exc)
        return []

def get_news(category: str = "general", count: int = 5) -> str:
    category = category.lower().strip()
    url = _FEEDS.get(category, _FEEDS["general"])
    headlines = _parse_rss(url, count)
    if not headlines:
        return f"Couldn't fetch {category} news right now."
    
    lines = [f"Here are the top {category} headlines:"]
    for i, h in enumerate(headlines, 1):
        lines.append(f"{i}. {h}")
    return " ".join(lines)

def get_tech_news() -> str:
    return get_news("tech")

def get_world_news() -> str:
    return get_news("world")
