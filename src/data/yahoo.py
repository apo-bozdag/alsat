"""Yahoo Finance veri katmani (yfinance) — hisse, endeks, emtia, doviz.

Binance katmaniyla ayni DataFrame semasini doner: time, open, high, low,
close, volume. Boylece indikator/sinyal/backtest motorlari hicbir degisiklik
olmadan tum varlik siniflarinda calisir.
"""
from datetime import datetime, timezone

import pandas as pd

# UI'daki dilim adlari -> yfinance interval adlari
_YF_INTERVAL = {"1d": "1d", "1w": "1wk", "1M": "1mo"}
# 500 civari mum hedefleyen veri donemleri
_YF_PERIOD = {"1d": "2y", "1w": "10y", "1M": "max"}


def _standardize(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df = raw.reset_index()
    time_col = "Date" if "Date" in df.columns else "Datetime"
    out = pd.DataFrame(
        {
            "time": pd.to_datetime(df[time_col], utc=True).astype("datetime64[ns, UTC]"),
            "open": df["Open"],
            "high": df["High"],
            "low": df["Low"],
            "close": df["Close"],
            "volume": df["Volume"].fillna(0),
        }
    )
    return out.dropna(subset=["close"]).reset_index(drop=True)


def get_klines(symbol: str, interval: str = "1d", limit: int = 500) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.Ticker(symbol).history(
        period=_YF_PERIOD[interval], interval=_YF_INTERVAL[interval], auto_adjust=True
    )
    return _standardize(raw).tail(limit).reset_index(drop=True)


def get_klines_range(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    import yfinance as yf

    start = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
    raw = yf.Ticker(symbol).history(
        start=start, end=end, interval=_YF_INTERVAL[interval], auto_adjust=True
    )
    return _standardize(raw)


def get_tickers(symbols: list[str]) -> dict[str, dict]:
    """Son fiyat + gunluk degisim % (binance.get_tickers_24h ile ayni sema)."""
    import yfinance as yf

    data = yf.download(
        symbols, period="5d", interval="1d", progress=False, auto_adjust=True
    )["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame(symbols[0])
    out = {}
    for sym in symbols:
        if sym not in data.columns:
            continue
        series = data[sym].dropna()
        if len(series) < 2:
            continue
        out[sym] = {
            "price": float(series.iloc[-1]),
            "change_pct": float((series.iloc[-1] / series.iloc[-2] - 1) * 100),
        }
    return out
