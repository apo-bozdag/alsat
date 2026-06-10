"""Basit long-only backtest: stratejinin gecmis isabetini olcer.

Giris: Donchian kirilim durumu (breakout) aktifken pozisyon yoksa kapanistan.
Cikis: oynakliga uyarlanan trailing stop (zirve - katsayi x ATR) veya SAT
sinyali. Sabit kar hedefi yok — trend kosturulur. Donem sonunda hala acik
pozisyon varsa son kapanisla degerlemeye katilir ("pozisyon acik" satiri).
"""
from datetime import datetime, timezone

import pandas as pd

from src.config import (
    BACKTEST_SENTIMENT_FLOOR,
    INDICATOR_WARMUP_BARS,
    INTERVAL_SECONDS,
    REGIME_MAP,
    WEIGHTS,
)


def _sentiment_series(symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame | None:
    """Gecmis F&G + funding verisinden kombine duygu skoru (gunluk seri).

    Skor = fng_oyu x agirlik + funding_oyu x agirlik. Asiri hirs ve kalabalik
    long ayni anda olusursa skor BACKTEST_SENTIMENT_FLOOR altina iner ve o
    gunlerde yeni giris yapilmaz (canli paneldeki kontrarian mantigin aynisi).
    """
    from src.data.binance import get_funding_history
    from src.data.news import fetch_fear_greed_history
    from src.signals.engine import _fng_vote, _funding_vote

    try:
        fng = fetch_fear_greed_history()
        funding = get_funding_history(symbol, start_ms, end_ms)
    except Exception:
        return None
    if fng.empty:
        return None

    fng["sent_fng"] = fng["fng"].map(_fng_vote) * WEIGHTS["fng"]
    out = fng[["time", "sent_fng"]]
    if not funding.empty:
        funding["sent_funding"] = funding["funding"].map(_funding_vote) * WEIGHTS["funding"]
        daily_funding = (
            funding.set_index("time")["sent_funding"].resample("1D").mean().reset_index()
        )
        out = pd.merge_asof(out, daily_funding, on="time", direction="backward")
    else:
        out["sent_funding"] = 0.0
    out["sentiment"] = out["sent_fng"] + out["sent_funding"].fillna(0.0)
    return out[["time", "sentiment"]]


def backtest_range(
    symbol: str, interval: str, start: datetime, end: datetime,
    provider: str = "binance",
) -> dict:
    """Secilen tarih araliginda backtest kosar (tum piyasalar).

    Indikatorlerin (ozellikle ust dilim EMA200'un) oturmasi icin aralik
    oncesinden warmup verisi cekilir; sinyaller tum seride hesaplanir ama
    islemler yalniz [start, end] icinde sayilir. Duygu filtresi (F&G+funding)
    yalniz kripto icin mevcut — diger piyasalarda gecmis duygu verisi yok.
    """
    from src.indicators.ta import add_indicators
    from src.signals import engine

    if provider == "yahoo":
        from src.data.yahoo import get_klines_range
    else:
        from src.data.binance import get_klines_range

    start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start
    end = end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    warmup_ms = INDICATOR_WARMUP_BARS * INTERVAL_SECONDS[interval] * 1000
    raw = get_klines_range(symbol, interval, start_ms - warmup_ms, end_ms)
    if raw.empty:
        return {"trades": pd.DataFrame(), "n_trades": 0, "win_rate": 0.0,
                "total_return_pct": 0.0, "buy_hold_pct": 0.0}
    df = add_indicators(raw)

    regime = None
    higher = REGIME_MAP.get(interval)
    if higher:
        h_warmup_ms = INDICATOR_WARMUP_BARS * INTERVAL_SECONDS[higher] * 1000
        higher_df = get_klines_range(symbol, higher, start_ms - h_warmup_ms, end_ms)
        if not higher_df.empty:
            regime = engine.regime_series(higher_df)

    scored = engine.compute_scores(df, regime)

    # Duygu katmani: gecmis F&G + funding skoru mumlara hizalanir (sadece kripto)
    sent = (
        _sentiment_series(symbol, start_ms - warmup_ms, end_ms)
        if provider == "binance" else None
    )
    if sent is not None:
        scored = pd.merge_asof(
            scored.sort_values("time"), sent.sort_values("time"),
            on="time", direction="backward",
        )
        scored["sentiment"] = scored["sentiment"].fillna(0.0)
    else:
        scored["sentiment"] = 0.0

    return run_backtest(scored[scored["time"] >= start].reset_index(drop=True))


def run_backtest(df: pd.DataFrame) -> dict:
    from src.signals.engine import trail_multiplier

    trades = []
    entry = stop = highest = None
    entry_time = None

    has_sentiment = "sentiment" in df.columns

    def close_position(exit_price, exit_time, reason):
        trades.append(
            {
                "giris_zamani": entry_time,
                "cikis_zamani": exit_time,
                "giris": entry,
                "cikis": exit_price,
                "getiri_pct": (exit_price / entry - 1) * 100,
                "neden": reason,
            }
        )

    for row in df.itertuples():
        if entry is None:
            sentiment_ok = (
                not has_sentiment or row.sentiment >= BACKTEST_SENTIMENT_FLOOR
            )
            if row.breakout and sentiment_ok and pd.notna(row.atr):
                entry, entry_time = row.close, row.time
                highest = row.close
                stop = entry - trail_multiplier(row.atr, row.close) * row.atr
            continue

        mult = trail_multiplier(row.atr, row.close)
        highest = max(highest, row.close)
        trail = max(stop, highest - mult * row.atr)
        stop = trail  # iz yalnizca yukari kayar

        exit_price, reason = None, None
        if row.low <= trail:
            exit_price, reason = trail, "trailing stop"
        elif row.signal == "SAT":
            exit_price, reason = row.close, "sinyal"

        if exit_price is not None:
            close_position(exit_price, row.time, reason)
            entry = None

    # Donem sonunda acik kalan pozisyon: son kapanisla degerle
    if entry is not None and len(df):
        last = df.iloc[-1]
        close_position(float(last["close"]), last["time"], "pozisyon acik")

    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        return {"trades": trades_df, "n_trades": 0, "win_rate": 0.0,
                "total_return_pct": 0.0, "buy_hold_pct": _buy_hold(df)}

    cumulative = (1 + trades_df["getiri_pct"] / 100).prod() - 1
    return {
        "trades": trades_df,
        "n_trades": len(trades_df),
        "win_rate": float((trades_df["getiri_pct"] > 0).mean() * 100),
        "total_return_pct": float(cumulative * 100),
        "buy_hold_pct": _buy_hold(df),
    }


def _buy_hold(df: pd.DataFrame) -> float:
    """Karsilastirma olcutu: ayni donemde al-ve-tut getirisi."""
    return float((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100)
