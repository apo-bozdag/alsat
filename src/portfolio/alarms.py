"""Fiyat/seviye alarmlari — UI'dan veya Telegram /alarm komutuyla kurulur.

Bildirici ~60 saniyede bir yalniz alarmli varliklarin fiyatina bakar;
seviye gecilince Telegram'a bildirir ve alarmi soner (tek atimlik).
Kayitlar .alarms.json'da.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

_STORE = Path(__file__).resolve().parents[2] / ".alarms.json"


def _load() -> list[dict]:
    try:
        return json.loads(_STORE.read_text())
    except Exception:
        return []


def _save(alarms: list[dict]) -> None:
    _STORE.write_text(json.dumps(alarms, indent=1, ensure_ascii=False))


def add(symbol: str, level: float, current_price: float) -> dict:
    """Alarm ekler; yon mevcut fiyata gore otomatik belirlenir."""
    alarm = {
        "id": max((a["id"] for a in _load()), default=0) + 1,
        "symbol": symbol,
        "level": level,
        "direction": "above" if level > current_price else "below",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
    }
    alarms = _load()
    alarms.append(alarm)
    _save(alarms)
    return alarm


def remove(alarm_id: int) -> None:
    _save([a for a in _load() if a["id"] != alarm_id])


def list_alarms() -> list[dict]:
    return _load()


def check(prices: dict[str, float]) -> list[dict]:
    """Tetiklenen alarmlari dondurur ve listeden dusurur.

    prices: {symbol: guncel_fiyat}
    """
    alarms = _load()
    triggered, remaining = [], []
    for a in alarms:
        price = prices.get(a["symbol"])
        if price is None:
            remaining.append(a)
            continue
        hit = price >= a["level"] if a["direction"] == "above" else price <= a["level"]
        if hit:
            triggered.append({**a, "price": price})
        else:
            remaining.append(a)
    if triggered:
        _save(remaining)
    return triggered
