"""Binance Public API veri katmani — API key gerektirmez."""
import json

import pandas as pd
import requests

from src.config import BINANCE_BASE, BINANCE_FUTURES, KLINE_LIMIT

_KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
]


def get_klines(symbol: str, interval: str = "1h", limit: int = KLINE_LIMIT) -> pd.DataFrame:
    """OHLCV mum verisi ceker. Kolonlar: time, open, high, low, close, volume."""
    resp = requests.get(
        f"{BINANCE_BASE}/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    df = pd.DataFrame(resp.json(), columns=_KLINE_COLUMNS)
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).astype("datetime64[ns, UTC]")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col])
    return df[["time", "open", "high", "low", "close", "volume"]]


def get_klines_range(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    """Belirli tarih araligindaki tum mumlari sayfali olarak ceker (1000'erli)."""
    frames = []
    cursor = start_ms
    while cursor < end_ms:
        resp = requests.get(
            f"{BINANCE_BASE}/klines",
            params={
                "symbol": symbol, "interval": interval,
                "startTime": cursor, "endTime": end_ms, "limit": 1000,
            },
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        frames.append(pd.DataFrame(batch, columns=_KLINE_COLUMNS))
        cursor = batch[-1][6] + 1  # son mumun close_time'indan devam et
        if len(batch) < 1000:
            break
    if not frames:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).astype("datetime64[ns, UTC]")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col])
    return df[["time", "open", "high", "low", "close", "volume"]]


def get_tickers_24h(symbols: list[str]) -> dict[str, dict]:
    """Tum coinlerin 24 saatlik fiyat/degisim bilgisini tek istekte ceker."""
    resp = requests.get(
        f"{BINANCE_BASE}/ticker/24hr",
        params={"symbols": json.dumps(symbols, separators=(",", ":"))},
        timeout=10,
    )
    resp.raise_for_status()
    return {
        item["symbol"]: {
            "price": float(item["lastPrice"]),
            "change_pct": float(item["priceChangePercent"]),
        }
        for item in resp.json()
    }


def get_funding_history(symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    """Gecmis funding oranlari (8 saatte bir, 2019'dan beri mevcut) — backtest icin."""
    frames = []
    cursor = start_ms
    while cursor < end_ms:
        resp = requests.get(
            f"{BINANCE_FUTURES}/fapi/v1/fundingRate",
            params={"symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": 1000},
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        frames.append(pd.DataFrame(batch))
        cursor = batch[-1]["fundingTime"] + 1
        if len(batch) < 1000:
            break
    if not frames:
        return pd.DataFrame(columns=["time", "funding"])
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True).astype("datetime64[ns, UTC]")
    df["funding"] = pd.to_numeric(df["fundingRate"])
    return df[["time", "funding"]]


def get_futures_sentiment(symbol: str) -> dict:
    """Turev piyasasi erken sinyal verileri (vadeli islemler, ucretsiz).

    funding: son funding orani (pozitif = longlar odeme yapiyor, kalabalik long)
    lsr:     buyuk oyuncularin long/short pozisyon orani
    taker:   son saatte piyasa emirli alim/satim hacim orani
    Endpoint erisilemezse ilgili deger None doner — skor o bileseni atlar.
    """
    out = {"funding": None, "lsr": None, "taker": None}
    try:
        resp = requests.get(
            f"{BINANCE_FUTURES}/fapi/v1/premiumIndex",
            params={"symbol": symbol}, timeout=10,
        )
        resp.raise_for_status()
        out["funding"] = float(resp.json()["lastFundingRate"])
    except Exception:
        pass
    try:
        resp = requests.get(
            f"{BINANCE_FUTURES}/futures/data/topLongShortPositionRatio",
            params={"symbol": symbol, "period": "1h", "limit": 1}, timeout=10,
        )
        resp.raise_for_status()
        out["lsr"] = float(resp.json()[0]["longShortRatio"])
    except Exception:
        pass
    try:
        resp = requests.get(
            f"{BINANCE_FUTURES}/futures/data/takerlongshortRatio",
            params={"symbol": symbol, "period": "1h", "limit": 1}, timeout=10,
        )
        resp.raise_for_status()
        out["taker"] = float(resp.json()[0]["buySellRatio"])
    except Exception:
        pass
    return out
