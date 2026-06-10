"""Sayfalarin ortak katmani: cache'li veri erisimi, yardimcilar, portfoy girisi.

Tum sayfalar veriyi buradan ceker; boylece sayfa gecislerinde ayni veri
yeniden indirilmez (st.cache_data surec genelinde gecerlidir).
"""
from datetime import datetime

import pandas as pd
import streamlit as st

from src.config import MARKETS, REGIME_MAP
from src.data import binance, cot, macro, news, panorama, yahoo
from src.indicators.ta import add_indicators
from src.portfolio import allocator
from src.sentiment import analyzer
from src.signals import backtest, engine


# ── Veri cache'leri ──────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def cached_klines(provider: str, symbol: str, interval: str) -> pd.DataFrame:
    if provider == "yahoo":
        return yahoo.get_klines(symbol, interval)
    return binance.get_klines(symbol, interval)


@st.cache_data(ttl=120, show_spinner=False)
def cached_tickers(market_name: str) -> dict:
    market = MARKETS[market_name]
    symbols = list(market["assets"])
    if market["provider"] == "yahoo":
        return yahoo.get_tickers(symbols)
    return binance.get_tickers_24h(symbols)


@st.cache_data(ttl=300, show_spinner=False)
def cached_futures(symbol: str) -> dict:
    return binance.get_futures_sentiment(symbol)


@st.cache_data(ttl=300, show_spinner=False)
def cached_fear_greed():
    return news.fetch_fear_greed()


@st.cache_data(ttl=900, show_spinner=False)
def cached_panorama_history() -> pd.DataFrame:
    return panorama.fetch_history()


@st.cache_data(ttl=600, show_spinner=False)
def cached_vix():
    return macro.fetch_vix()


@st.cache_data(ttl=600, show_spinner=False)
def cached_crypto_global():
    return macro.fetch_crypto_global()


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def cached_cot():
    return cot.fetch_cot()


@st.cache_data(ttl=600, show_spinner="Gecmis veri cekiliyor, backtest kosuyor...")
def cached_backtest(provider: str, symbol: str, interval: str,
                    start_iso: str, end_iso: str) -> dict:
    return backtest.backtest_range(
        symbol, interval,
        datetime.fromisoformat(start_iso), datetime.fromisoformat(end_iso),
        provider=provider,
    )


@st.cache_resource(show_spinner="FinBERT modeli yukleniyor (ilk seferde ~440MB iner)...")
def finbert_model():
    return analyzer.load_model()


@st.cache_data(ttl=300, show_spinner="Haberler cekiliyor ve analiz ediliyor...")
def cached_scored_news() -> list[dict]:
    return analyzer.score_news(finbert_model(), news.fetch_news())


@st.cache_data(ttl=120, show_spinner=False)
def analyzed(provider: str, symbol: str, interval: str) -> pd.DataFrame:
    """Mum verisi + indikatorler + rejim filtreli sinyal skorlari."""
    df = add_indicators(cached_klines(provider, symbol, interval))
    higher = REGIME_MAP.get(interval)
    regime = None
    if higher:
        higher_df = cached_klines(provider, symbol, higher)
        if not higher_df.empty:
            regime = engine.regime_series(higher_df)
    return engine.compute_scores(df, regime)


# ── Turetilmis yapilar ───────────────────────────────────────────────────
def news_bundle() -> dict:
    """Haberler + turetilmis skorlar tek pakette."""
    scored = cached_scored_news()
    return {
        "scored": scored,
        "coin_scores": analyzer.aggregate_coin_scores(scored),
        "macro": analyzer.aggregate_macro_score(scored),
        "geo": analyzer.aggregate_geo_score(scored),
    }


def build_extras(provider: str, symbol: str, df: pd.DataFrame, bundle: dict) -> dict:
    """Erken sinyal bilesenleri. Turev verisi ve F&G yalniz kripto icin var."""
    is_crypto = provider == "binance"
    fut = cached_futures(symbol) if is_crypto else {"funding": None, "lsr": None, "taker": None}
    fng = cached_fear_greed() if is_crypto else None
    return {
        "news": bundle["coin_scores"].get(symbol, 0.0),
        "macro": bundle["macro"],
        "geo": bundle["geo"],
        "funding": fut["funding"],
        "lsr": fut["lsr"],
        "taker": fut["taker"],
        "fng": fng["value"] if fng else None,
        "regime": int(df["regime"].iloc[-1]) if len(df) else 0,
    }


def recommendation_for(market_name: str, symbol: str, interval: str, bundle: dict) -> dict:
    provider = MARKETS[market_name]["provider"]
    df = analyzed(provider, symbol, interval)
    return engine.current_recommendation(df, build_extras(provider, symbol, df, bundle))


# ── UI yardimcilari ──────────────────────────────────────────────────────
def fmt_price(p: float | None, provider: str = "binance") -> str:
    """Buyuklugune gore hassasiyet; kriptoda $ on eki."""
    if p is None:
        return "—"
    cur = "$" if provider == "binance" else ""
    if p >= 1000:
        return f"{cur}{p:,.0f}"
    if p >= 1:
        return f"{cur}{p:,.2f}"
    return f"{cur}{p:.4f}"


def portfolio_sidebar() -> tuple[float, float]:
    """Sermaye ve risk girisi — tum sayfalarda sidebar altinda gorunur."""
    st.sidebar.divider()
    capital = st.sidebar.number_input(
        "💰 Sermaye ($)", min_value=100.0, value=allocator.load_capital(),
        step=500.0, key="capital_input",
        help="Pozisyon boyutu ve dagilim onerisi bu tutara gore hesaplanir.",
    )
    risk_pct = st.sidebar.select_slider(
        "Islem basina risk", options=[0.5, 1.0, 2.0], value=1.0,
        format_func=lambda v: f"%{v}", key="risk_input",
        help="Profesyonel standart %1-2: stop yenirse kaybedilecek sermaye orani.",
    ) / 100
    allocator.save_capital(capital)
    return capital, risk_pct


def overview_rows(bundle: dict) -> list[dict]:
    """Tum piyasalarin sinyal/rejim ozeti — Genel Bakis tablosu ve dagilim onerisi."""
    rows = []
    for mk_name, mk in MARKETS.items():
        try:
            mk_tickers = cached_tickers(mk_name)
        except Exception:
            mk_tickers = {}
        for sym, asset in mk["assets"].items():
            try:
                df_o = analyzed(mk["provider"], sym, "1d")
                rec_o = engine.current_recommendation(
                    df_o, build_extras(mk["provider"], sym, df_o, bundle)
                )
                rows.append(
                    {
                        "Piyasa": mk_name,
                        "Varlik": asset["name"],
                        "Gunluk %": round(mk_tickers.get(sym, {}).get("change_pct", 0.0), 2),
                        "Sinyal": {"AL": "🟢 AL", "SAT": "🔴 SAT", "BEKLE": "⚪ BEKLE"}[rec_o["action"]],
                        "Rejim": {1: "🐂", 0: "➖", -1: "🐻"}[rec_o["regime"]],
                        "Skor": round(rec_o["score"], 2),
                        "_symbol": sym,
                        "_market": mk_name,
                    }
                )
            except Exception:
                continue
    return rows


def goto_analysis(market_name: str, symbol: str) -> None:
    """Genel Bakis'tan Analiz sayfasina secili varlikla gecis."""
    st.session_state["goto_market"] = market_name
    st.session_state["goto_symbol"] = symbol
    st.switch_page(st.session_state["_page_analysis"])
