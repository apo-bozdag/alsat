"""Islem gunlugu — pro'larin bir numarali aliskanligi: her islemi kaydet.

Kayitlar .journal.json'da tutulur. Acik pozisyonlar kapatilana kadar izlenir;
kapali islemlerden isabet orani ve toplam K/Z istatistigi cikarilir.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

_STORE = Path(__file__).resolve().parents[2] / ".journal.json"


def _load() -> list[dict]:
    try:
        return json.loads(_STORE.read_text())
    except Exception:
        return []


def _save(entries: list[dict]) -> None:
    _STORE.write_text(json.dumps(entries, indent=1, ensure_ascii=False))


def open_position(symbol: str, name: str, entry: float, stop: float,
                  qty: float, note: str = "") -> None:
    entries = _load()
    entries.append(
        {
            "id": max((e["id"] for e in entries), default=0) + 1,
            "symbol": symbol,
            "name": name,
            "opened_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "entry": entry,
            "stop": stop,
            "qty": qty,
            "note": note,
            "closed_at": None,
            "exit": None,
        }
    )
    _save(entries)


def close_position(entry_id: int, exit_price: float) -> None:
    entries = _load()
    for e in entries:
        if e["id"] == entry_id and e["closed_at"] is None:
            e["closed_at"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
            e["exit"] = exit_price
    _save(entries)


def open_positions() -> list[dict]:
    return [e for e in _load() if e["closed_at"] is None]


def closed_positions() -> list[dict]:
    out = []
    for e in _load():
        if e["closed_at"] is None:
            continue
        pnl = (e["exit"] - e["entry"]) * e["qty"]
        out.append({**e, "pnl": pnl, "pnl_pct": (e["exit"] / e["entry"] - 1) * 100})
    return out


def stats() -> dict | None:
    closed = closed_positions()
    if not closed:
        return None
    wins = [e for e in closed if e["pnl"] > 0]
    return {
        "n": len(closed),
        "win_rate": len(wins) / len(closed) * 100,
        "total_pnl": sum(e["pnl"] for e in closed),
        "avg_pct": sum(e["pnl_pct"] for e in closed) / len(closed),
    }
