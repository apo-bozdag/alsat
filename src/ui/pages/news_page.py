"""📰 Haberler — tum kaynaklar, sentiment rozetleri, derin analiz."""
import streamlit as st

from src.config import ALL_ASSETS
from src.ui import news_panel, shared


def page() -> None:
    st.title("📰 Haberler")
    bundle = shared.news_bundle()

    # Varlik filtresi icin: son analiz edilen varlik ya da BTC
    selected = st.session_state.get("last_calc", {}).get("symbol", "BTCUSDT")
    if selected not in ALL_ASSETS:
        selected = "BTCUSDT"
    news_panel.render(bundle["scored"], selected, bundle["macro"])
