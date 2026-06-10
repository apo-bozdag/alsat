"""Sinyal karnesi — sistemin kendi sinyallerinin otomatik kagit-takibi.

Bildirici her taramada sinyalleri buraya bildirir:
- Bir varlik AL'a gectiginde o anki fiyattan SANAL pozisyon acilir.
- Sinyal AL'dan ciktiginda (BEKLE/SAT) o anki fiyattan kapanir.
Boylece "algoritma canlida gercekte ne yapiyor?" sorusunun durust cevabi
birikir — backtest'in canli dogrulamasi. Kayitlar .scorecard.json'da.

Not: Kapanis fiyati tarama anindaki fiyattir (30 dk cozunurluk); gercek
trailing stop seviyesinden sapabilir. Karne yon dogrulugunu olcer,
kuruşu kurusuna getiriyi degil.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

_STORE = Path(__file__).resolve().parents[2] / ".scorecard.json"


def _load() -> dict:
    try:
        return json.loads(_STORE.read_text())
    except Exception:
        return {"open": {}, "closed": [], "events": []}


def _save(data: dict) -> None:
    _STORE.write_text(json.dumps(data, indent=1, ensure_ascii=False))


def record_scan(actions_prices: dict[str, tuple[str, float]]) -> list[str]:
    """Tarama sonucunu isler; acilan/kapanan sanal pozisyon ozetleri dondurur.

    actions_prices: {symbol: (action, price)}
    """
    data = _load()
    now = datetime.now(timezone.utc).isoformat(timespec="minutes")
    notes = []

    for symbol, (action, price) in actions_prices.items():
        is_open = symbol in data["open"]
        if action == "AL" and not is_open and price:
            data["open"][symbol] = {"entry": price, "opened_at": now}
            data["events"].append({"time": now, "symbol": symbol, "event": "AL", "price": price})
            notes.append(f"sanal giris: {symbol} @ {price:,.4g}")
        elif action != "AL" and is_open and price:
            pos = data["open"].pop(symbol)
            ret_pct = (price / pos["entry"] - 1) * 100
            data["closed"].append(
                {
                    "symbol": symbol,
                    "opened_at": pos["opened_at"],
                    "closed_at": now,
                    "entry": pos["entry"],
                    "exit": price,
                    "ret_pct": ret_pct,
                }
            )
            data["events"].append({"time": now, "symbol": symbol, "event": "KAPANIS", "price": price})
            notes.append(f"sanal cikis: {symbol} @ {price:,.4g} ({ret_pct:+.1f}%)")

    data["events"] = data["events"][-200:]  # log sismesin
    _save(data)
    return notes


def open_positions() -> dict:
    return _load()["open"]


def closed_trades() -> list[dict]:
    return _load()["closed"]


def events_since(iso_time: str) -> list[dict]:
    """Sabah raporu icin: belirli andan sonraki sinyal olaylari."""
    return [e for e in _load()["events"] if e["time"] >= iso_time]


def stats() -> dict | None:
    closed = closed_trades()
    if not closed:
        return None
    wins = [t for t in closed if t["ret_pct"] > 0]
    return {
        "n": len(closed),
        "win_rate": len(wins) / len(closed) * 100,
        "avg_ret": sum(t["ret_pct"] for t in closed) / len(closed),
        "total_ret": (
            __import__("math").prod(1 + t["ret_pct"] / 100 for t in closed) - 1
        ) * 100,
    }
