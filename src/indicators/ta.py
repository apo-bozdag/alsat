"""Teknik indikatorler — saf pandas, harici TA kutuphanesi yok."""
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder yontemiyle RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - 100 / (1 + rs)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD cizgisi, sinyal cizgisi ve histogram dondurur."""
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range — stop/hedef seviyeleri icin volatilite olcusu."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Sinyal motorunun ihtiyac duydugu tum indikatorleri DataFrame'e ekler."""
    out = df.copy()
    out["ema20"] = ema(out["close"], 20)
    out["ema50"] = ema(out["close"], 50)
    out["rsi"] = rsi(out["close"])
    out["macd_line"], out["macd_signal"], out["macd_hist"] = macd(out["close"])
    out["atr"] = atr(out)
    out["vol_ma20"] = out["volume"].rolling(20).mean()
    # Donchian ust bandi: onceki N mumun en yuksek kapanisi (kirilim girisi icin)
    out["hh20"] = out["close"].rolling(20).max().shift(1)
    return out
