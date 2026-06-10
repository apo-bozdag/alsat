"""Haber kaynaklari: RSS akislari + Fear & Greed endeksi (hepsi ucretsiz, key'siz)."""
import calendar
from datetime import datetime, timezone

import feedparser
import requests

from src.config import FNG_URL, RSS_FEEDS


def fetch_news(max_per_feed: int = 20) -> list[dict]:
    """Tum RSS kaynaklarindan haberleri ceker, yeniden eskiye siralar.

    Bir kaynak erisilemezse atlanir — tek kaynak coktu diye uygulama durmaz.
    """
    items = []
    for source, meta in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(meta["url"])
        except Exception:
            continue
        for entry in feed.entries[:max_per_feed]:
            published = _entry_time(entry)
            if published is None:
                continue
            items.append(
                {
                    "title": entry.get("title", "").strip(),
                    "link": entry.get("link", ""),
                    "source": source,
                    "category": meta["category"],
                    "lang": meta.get("lang", "en"),
                    "published": published,
                }
            )
    items.sort(key=lambda x: x["published"], reverse=True)
    return items


def _entry_time(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


def fetch_fear_greed_history() -> "pd.DataFrame":
    """Korku & Hirs endeksinin tum gunluk gecmisi (2018'den beri) — backtest icin."""
    import pandas as pd

    resp = requests.get("https://api.alternative.me/fng/?limit=0", timeout=15)
    resp.raise_for_status()
    rows = resp.json()["data"]
    df = pd.DataFrame(
        {
            "time": pd.to_datetime([int(r["timestamp"]) for r in rows], unit="s", utc=True),
            "fng": [int(r["value"]) for r in rows],
        }
    )
    # farkli kaynaklarin zaman cozunurlugu (s/ms) merge_asof'ta uyusmali
    df["time"] = df["time"].astype("datetime64[ns, UTC]")
    return df.sort_values("time").reset_index(drop=True)


def fetch_fear_greed() -> dict | None:
    """Alternative.me Fear & Greed endeksi: 0 (asiri korku) - 100 (asiri hirs)."""
    try:
        resp = requests.get(FNG_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()["data"][0]
        return {"value": int(data["value"]), "label": data["value_classification"]}
    except Exception:
        return None
