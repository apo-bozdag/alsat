"""Piyasa geneli risk gostergeleri: VIX, BTC dominansi, stablecoin payi.

Hepsi ucretsiz: VIX yfinance'tan, kripto genel verisi CoinGecko'dan.
"""
import requests


def fetch_vix() -> dict | None:
    """VIX (borsa korku endeksi) son degeri + yorumu."""
    import yfinance as yf

    try:
        hist = yf.Ticker("^VIX").history(period="5d", interval="1d", auto_adjust=True)
        if hist.empty:
            return None
        value = float(hist["Close"].iloc[-1])
    except Exception:
        return None
    if value < 15:
        label = "rehavet"
    elif value < 25:
        label = "normal"
    elif value < 30:
        label = "gergin"
    else:
        label = "panik"
    return {"value": value, "label": label}


def fetch_crypto_global() -> dict | None:
    """BTC dominansi ve stablecoin (USDT) payi — para nereye siginmis?

    Dominans artiyor + altcoinler dususte = riskten kacis BTC'ye;
    USDT payi artiyor = para tamamen kenara cekiliyor.
    """
    try:
        resp = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        resp.raise_for_status()
        data = resp.json()["data"]
        return {
            "btc_dominance": float(data["market_cap_percentage"]["btc"]),
            "usdt_share": float(data["market_cap_percentage"].get("usdt", 0.0)),
            "mcap_change_24h": float(data["market_cap_change_percentage_24h_usd"]),
        }
    except Exception:
        return None
