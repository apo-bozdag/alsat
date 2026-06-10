"""Portfoy seviyesi backtest — dagilim kurallariyla TUM sepetin simulasyonu.

Tek varlik backtest'i "bu varlikta strateji ne yapardi" sorusunu cevaplar;
bu modul "dagilim onerisi kurallariyla butun parayi yonetseydik ne olurdu"
sorusunu cevaplar. Kurallar canli paneldekiyle ayni:
- Giris: Donchian kirilimi + ust dilim rejimi pozitif (gunluk dilim)
- Pozisyon buyuklugu: sermayenin %15'i (varlik tavani), piyasa basina %50
- Cikis: oynakliga uyarlanan trailing stop (kapanis bazli)
- Bos kalan para nakitte bekler

Yurutme gunluk kapanislarla yapilir (porfoy duzeyinde gun ici low/high
takibi yaniltici olur); tek varlik backtest'inden bu yuzden hafifce sapar.
"""
from datetime import datetime, timezone

import pandas as pd

from src.config import (
    INDICATOR_WARMUP_BARS,
    INTERVAL_SECONDS,
    MARKETS,
    REGIME_MAP,
)
from src.indicators.ta import add_indicators
from src.signals import engine

MAX_PER_ASSET = 0.15
MAX_PER_MARKET = 0.50


def _prep_asset(provider: str, symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame | None:
    if provider == "yahoo":
        from src.data.yahoo import get_klines_range
    else:
        from src.data.binance import get_klines_range

    warmup = INDICATOR_WARMUP_BARS * INTERVAL_SECONDS["1d"] * 1000
    try:
        df = get_klines_range(symbol, "1d", start_ms - warmup, end_ms)
        if len(df) < 60:
            return None
        df = add_indicators(df)
        higher = REGIME_MAP["1d"]
        h_warmup = INDICATOR_WARMUP_BARS * INTERVAL_SECONDS[higher] * 1000
        higher_df = get_klines_range(symbol, higher, start_ms - h_warmup, end_ms)
        regime = engine.regime_series(higher_df) if not higher_df.empty else None
        scored = engine.compute_scores(df, regime)
        scored["date"] = scored["time"].dt.normalize()
        return scored[["date", "close", "atr", "breakout"]]
    except Exception:
        return None


def run_portfolio_backtest(start: datetime, end: datetime,
                           initial_capital: float = 10_000.0) -> dict:
    start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start
    end = end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    # Tum varliklarin gunluk serilerini topla
    frames, market_of = {}, {}
    for mk_name, mk in MARKETS.items():
        for symbol in mk["assets"]:
            df = _prep_asset(mk["provider"], symbol, start_ms, end_ms)
            if df is not None:
                frames[symbol] = df.set_index("date")
                market_of[symbol] = mk_name
    if not frames:
        return {"error": "Hicbir varlik icin veri alinamadi."}

    all_dates = sorted(
        {d for df in frames.values() for d in df.index if d >= pd.Timestamp(start)}
    )

    cash = initial_capital
    positions: dict[str, dict] = {}  # symbol -> {qty, entry, hi, stop}
    equity_curve, trades = [], []

    for day in all_dates:
        # Gunun fiyatlari
        prices = {
            s: float(df.loc[day, "close"]) for s, df in frames.items() if day in df.index
        }

        # 1) Cikislar: trailing stop (kapanis bazli, iz yalniz yukari)
        for symbol in list(positions):
            if symbol not in prices:
                continue
            pos = positions[symbol]
            row = frames[symbol].loc[day]
            price, atr = prices[symbol], float(row["atr"])
            mult = engine.trail_multiplier(atr, price)
            pos["hi"] = max(pos["hi"], price)
            pos["stop"] = max(pos["stop"], pos["hi"] - mult * atr)
            if price <= pos["stop"]:
                cash += pos["qty"] * price
                trades.append(
                    {
                        "Varlik": symbol,
                        "Cikis": day.date().isoformat(),
                        "Getiri %": round((price / pos["entry"] - 1) * 100, 2),
                    }
                )
                del positions[symbol]

        # 2) Guncel ozkaynak
        equity = cash + sum(
            pos["qty"] * prices.get(s, pos["entry"]) for s, pos in positions.items()
        )

        # 3) Girisler: kirilim durumundaki varliklar, tavanlara uyarak
        for symbol, df in frames.items():
            if symbol in positions or symbol not in prices or day not in df.index:
                continue
            if not bool(df.loc[day, "breakout"]):
                continue
            market_exposure = sum(
                pos["qty"] * prices.get(s, pos["entry"])
                for s, pos in positions.items()
                if market_of[s] == market_of[symbol]
            )
            budget = min(
                MAX_PER_ASSET * equity,
                MAX_PER_MARKET * equity - market_exposure,
                cash,
            )
            if budget < equity * 0.02:  # anlamsiz kucuk pozisyon acma
                continue
            price = prices[symbol]
            atr = float(df.loc[day, "atr"])
            qty = budget / price
            positions[symbol] = {
                "qty": qty, "entry": price, "hi": price,
                "stop": price - engine.trail_multiplier(atr, price) * atr,
            }
            cash -= budget

        equity_curve.append({"date": day, "equity": equity})

    curve = pd.DataFrame(equity_curve).set_index("date")
    final = float(curve["equity"].iloc[-1])
    peak = curve["equity"].cummax()
    max_dd = float(((curve["equity"] / peak) - 1).min() * 100)

    return {
        "curve": curve,
        "trades": pd.DataFrame(trades),
        "final_equity": final,
        "total_return_pct": (final / initial_capital - 1) * 100,
        "max_drawdown_pct": max_dd,
        "n_trades": len(trades),
        "win_rate": (
            float((pd.DataFrame(trades)["Getiri %"] > 0).mean() * 100) if trades else 0.0
        ),
        "open_positions": len(positions),
    }
