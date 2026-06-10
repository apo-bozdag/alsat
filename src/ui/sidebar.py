"""Sol panel: piyasa secimi, varlik listesi + sinyal rozetleri, Fear & Greed."""
import streamlit as st

from src.config import MARKETS

_BADGE = {"AL": "🟢 AL", "SAT": "🔴 SAT", "BEKLE": "⚪ BEKLE"}


def select_market() -> str:
    """Piyasa secimi — analiz sayfasinin geri kalani bu secime gore veri ceker."""
    return st.sidebar.selectbox(
        "Piyasa", list(MARKETS), label_visibility="collapsed", key="market_select"
    )


def render(market_name: str, tickers: dict, actions: dict[str, str],
           fear_greed: dict | None) -> tuple[str, str]:
    """Sidebar'in kalanini cizer; secili (sembol, dilim) dondurur."""
    market = MARKETS[market_name]
    assets = market["assets"]

    interval = st.sidebar.radio(
        "Zaman dilimi", market["timeframes"],
        index=market["timeframes"].index(market["default_tf"]),
        horizontal=True, key=f"tf_{market_name}",
    )

    st.sidebar.subheader("Varliklar")
    symbol = st.sidebar.radio(
        "Varlik sec",
        list(assets),
        format_func=lambda s: _asset_label(s, assets, tickers, actions),
        label_visibility="collapsed",
        key=f"asset_{market_name}",
    )

    st.sidebar.divider()
    if fear_greed:
        emoji = "😨" if fear_greed["value"] < 30 else "😐" if fear_greed["value"] < 60 else "🤑"
        st.sidebar.metric(
            "Korku & Hirs Endeksi (kripto)",
            f"{fear_greed['value']} {emoji}",
            fear_greed["label"],
            delta_color="off",
        )
    return symbol, interval


def _asset_label(symbol: str, assets: dict, tickers: dict, actions: dict) -> str:
    short = assets[symbol]["short"]
    ticker = tickers.get(symbol)
    badge = _BADGE.get(actions.get(symbol, ""), "")
    if not ticker:
        return f"{short} · {badge}"
    return f"{short}  {ticker['change_pct']:+.2f}%  ·  {badge}"
