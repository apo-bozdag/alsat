"""Uc katmanli confluence sinyal motoru.

1. REJIM (ust zaman dilimi): EMA50/200 ile piyasa yonu belirlenir. Dusus
   rejiminde AL, yukselis rejiminde SAT sinyali uretilmez — trende karsi
   islem en buyuk kayip kaynagidir.
2. TETIK (secili dilim): trend + RSI + MACD + hacim oylamasi. Grafik
   isaretleri ve backtest bu katmani kullanir (gecmisi hesaplanabilir).
3. ERKEN SINYAL (sadece guncel oneri): turev piyasasi (funding, long/short,
   taker) + haber + makro + Korku&Hirs. Bunlar fiyattan once hareket eder
   ama gecmis degerlerine sahip olmadigimiz icin grafige cizilmez.
"""
import numpy as np
import pandas as pd

from src.config import (
    BUY_THRESHOLD,
    FUNDING_EXTREME,
    FUNDING_HOT,
    LSR_CROWDED_LONG,
    LSR_CROWDED_SHORT,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    CALM_ATR_PCT,
    SELL_THRESHOLD,
    TRAIL_ATR_MULT_CALM,
    TRAIL_ATR_MULT_VOLATILE,
    VOLUME_SPIKE,
    WEIGHTS,
)


def trail_multiplier(atr: float, price: float) -> float:
    """Oynakliga uyarlanan trailing stop katsayisi."""
    if price <= 0:
        return TRAIL_ATR_MULT_VOLATILE
    return TRAIL_ATR_MULT_CALM if atr / price < CALM_ATR_PCT else TRAIL_ATR_MULT_VOLATILE


def component_votes(df: pd.DataFrame) -> pd.DataFrame:
    """Fiyat bilesenlerinin mum bazinda oyu: +1 (al), -1 (sat), 0 veya ara deger."""
    votes = pd.DataFrame(index=df.index)

    # Trend: EMA20 EMA50'nin ustundeyse yukari trend
    votes["trend"] = np.where(df["ema20"] > df["ema50"], 1.0, -1.0)

    # RSI: asiri bolgeden DONUS aninda oy verir (bolgede beklemek yetmez)
    rsi_prev = df["rsi"].shift(1)
    votes["rsi"] = np.select(
        [
            (rsi_prev < RSI_OVERSOLD) & (df["rsi"] > rsi_prev),
            (rsi_prev > RSI_OVERBOUGHT) & (df["rsi"] < rsi_prev),
        ],
        [1.0, -1.0],
        default=0.0,
    )

    # MACD: histogram isaret degisimi tam oy, mevcut yon yarim oy
    hist, hist_prev = df["macd_hist"], df["macd_hist"].shift(1)
    votes["macd"] = np.select(
        [(hist > 0) & (hist_prev <= 0), (hist < 0) & (hist_prev >= 0)],
        [1.0, -1.0],
        default=0.5 * np.sign(hist),
    )

    # Hacim: ortalamanin uzerinde patlama varsa mum yonunde onay
    spike = df["volume"] > VOLUME_SPIKE * df["vol_ma20"]
    votes["volume"] = np.where(spike, np.sign(df["close"] - df["open"]), 0.0)

    return votes


# ── Rejim katmani ────────────────────────────────────────────────────────

def regime_series(higher_df: pd.DataFrame) -> pd.Series:
    """Ust zaman dilimi DataFrame'inden mum bazinda rejim: +1 / 0 / -1.

    Yeterli veri varsa EMA50/EMA200, yoksa (orn. aylik mumlar) EMA20/EMA50.
    """
    close = higher_df["close"]
    if len(higher_df) >= 210:
        fast = close.ewm(span=50, adjust=False).mean()
        slow = close.ewm(span=200, adjust=False).mean()
    else:
        fast = close.ewm(span=20, adjust=False).mean()
        slow = close.ewm(span=50, adjust=False).mean()
    bull = (close > slow) & (fast > slow)
    bear = (close < slow) & (fast < slow)
    values = np.select([bull, bear], [1, -1], default=0)
    return pd.Series(values, index=higher_df["time"], name="regime")


def align_regime(df: pd.DataFrame, regime: pd.Series | None) -> pd.Series:
    """Ust dilim rejimini secili dilimin mumlarina hizalar (geriye donuk)."""
    if regime is None:
        return pd.Series(0, index=df.index)
    merged = pd.merge_asof(
        df[["time"]].reset_index(),
        regime.reset_index().rename(columns={"index": "r_time", "time": "r_time"}),
        left_on="time",
        right_on="r_time",
        direction="backward",
    )
    return merged["regime"].fillna(0).set_axis(df.index)


# ── Tetik katmani ────────────────────────────────────────────────────────

def compute_scores(df: pd.DataFrame, regime: pd.Series | None = None) -> pd.DataFrame:
    """Fiyat skoru + rejim filtreli AL/SAT isaretlerini ekler."""
    out = df.copy()
    votes = component_votes(out)
    out["score"] = sum(votes[c] * WEIGHTS[c] for c in votes.columns)
    out["regime"] = align_regime(out, regime)

    # GIRIS: Donchian ust bant kirilimi + ust dilim rejimi pozitif.
    # 8 coin x 3 yil taramada skor-kesisimli girisi acik farkla yendi
    # (ortalama +15 vs -7) ve dusus derinligini yari yariya azaltti.
    out["breakout"] = (out["close"] > out["hh20"]) & (out["regime"] > 0)

    # CIKIS sinyali: skor guclu negatife donerse (notr/negatif rejimde)
    sell_th = SELL_THRESHOLD * sum(WEIGHTS[c] for c in votes.columns) / sum(WEIGHTS.values())
    prev = out["score"].shift(1)
    raw_sell = (out["score"] <= sell_th) & (prev > sell_th)

    # Grafik isaretleri: kirilimin ILK mumu AL, satis kesisimi SAT
    fresh_breakout = out["breakout"] & ~out["breakout"].shift(1, fill_value=False)
    out["signal"] = np.select(
        [fresh_breakout, raw_sell & (out["regime"] <= 0)],
        ["AL", "SAT"],
        default="",
    )
    return out


# ── Erken sinyal oylari ─────────────────────────────────────────────────

def _funding_vote(rate: float | None) -> float:
    """Kontrarian: asiri pozitif funding = kalabalik long = dusus riski."""
    if rate is None:
        return 0.0
    if rate >= FUNDING_EXTREME:
        return -1.0
    if rate >= FUNDING_HOT:
        return -0.5
    if rate <= -FUNDING_EXTREME:
        return 1.0
    if rate <= -FUNDING_HOT / 2:
        return 0.5
    return 0.0


def _lsr_vote(ratio: float | None) -> float:
    """Kontrarian: buyuk oyuncular asiri tek yonde toplandiysa ters yon riski."""
    if ratio is None:
        return 0.0
    if ratio >= LSR_CROWDED_LONG:
        return -1.0
    if ratio <= LSR_CROWDED_SHORT:
        return 1.0
    return 0.0


def _taker_vote(ratio: float | None) -> float:
    """Momentum: piyasa emirli alimlar satislardan fazlaysa yukari baski."""
    if ratio is None:
        return 0.0
    return float(np.clip((ratio - 1.0) * 2.0, -1.0, 1.0))


def _fng_vote(value: int | None) -> float:
    """Kontrarian: asiri korku tarihsel olarak alim bolgesi, asiri hirs satis."""
    if value is None:
        return 0.0
    if value <= 20:
        return 1.0
    if value <= 35:
        return 0.5
    if value >= 80:
        return -1.0
    if value >= 65:
        return -0.5
    return 0.0


def current_recommendation(df: pd.DataFrame, extras: dict | None = None) -> dict:
    """Tum katmanlari birlestirip guncel oneri ve risk seviyeleri uretir.

    extras: {news, macro, funding, lsr, taker, fng, regime} — eksik anahtar
    veya None deger o bilesenin 0 (notr) sayilmasi demektir.
    """
    extras = extras or {}
    last = df.iloc[-1]
    votes = component_votes(df).iloc[-1]

    breakdown = {c: float(votes[c] * WEIGHTS[c]) for c in votes.index}
    breakdown["news"] = float(np.clip(extras.get("news") or 0.0, -1, 1) * WEIGHTS["news"])
    breakdown["macro"] = float(np.clip(extras.get("macro") or 0.0, -1, 1) * WEIGHTS["macro"])
    breakdown["geo"] = float(np.clip(extras.get("geo") or 0.0, -1, 0) * WEIGHTS["geo"])
    breakdown["funding"] = _funding_vote(extras.get("funding")) * WEIGHTS["funding"]
    breakdown["lsr"] = _lsr_vote(extras.get("lsr")) * WEIGHTS["lsr"]
    breakdown["taker"] = _taker_vote(extras.get("taker")) * WEIGHTS["taker"]
    breakdown["fng"] = _fng_vote(extras.get("fng")) * WEIGHTS["fng"]

    score = sum(breakdown.values())
    regime = int(extras.get("regime") or 0)
    price, atr_val = float(last["close"]), float(last["atr"])
    breakout_level = float(last["hh20"]) if pd.notna(last["hh20"]) else None
    above_band = breakout_level is not None and price > breakout_level

    # Oncelik sirasi: cikis kosulu > kirilim girisi > rejim engeli > bekle
    gated = False
    if score <= SELL_THRESHOLD and regime <= 0:
        action = "SAT"
    elif above_band and regime > 0:
        action = "AL"
    elif above_band and regime <= 0:
        action, gated = "BEKLE", True  # kirilim var ama ust dilim onaylamiyor
    else:
        action = "BEKLE"

    return {
        "action": action,
        "score": float(score),
        "breakdown": breakdown,
        "regime": regime,
        "regime_gated": gated,
        "price": price,
        "stop": price - trail_multiplier(atr_val, price) * atr_val,
        "breakout_level": breakout_level,
    }
