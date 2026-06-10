"""AL-SAT — Cok piyasali sinyal dashboard'u (kripto, ABD, BIST, emtia/doviz).

Calistirma: streamlit run app.py

Sayfa mimarisi (kapsamlarina gore ayrik):
- 🌍 Genel Bakis: ACILIS — secim gerektirmeyen kus bakisi dunya gorunumu
- 📊 Analiz: piyasa/varlik secimi + sinyal + grafik + pozisyon + backtest
- 📰 Haberler: tum kaynaklar + sentiment + derin analiz
- 📒 Gunluk: islem kayitlari ve performans
"""
import streamlit as st

from src.ui import shared
from src.ui.pages import analysis, journal_page, news_page, overview

st.set_page_config(page_title="AL-SAT", page_icon="📈", layout="wide")

page_overview = st.Page(overview.page, title="Genel Bakis", icon="🌍",
                        url_path="genel-bakis", default=True)
page_analysis = st.Page(analysis.page, title="Analiz", icon="📊", url_path="analiz")
page_news = st.Page(news_page.page, title="Haberler", icon="📰", url_path="haberler")
page_journal = st.Page(journal_page.page, title="Gunluk", icon="📒", url_path="gunluk")

# Genel Bakis'taki tiklanabilir tablo bu referansla Analiz'e gecis yapar
st.session_state["_page_analysis"] = page_analysis

nav = st.navigation([page_overview, page_analysis, page_news, page_journal])

nav.run()

# Sermaye/risk girisi her sayfada sidebar'in altinda
shared.portfolio_sidebar()


@st.fragment(run_every="60s")
def _auto_refresh_tick():
    """Toggle acikken 60 saniyede bir tum sayfayi tazeler (cache ttl'leri
    zaten kisa; bu sadece yeniden cizimi tetikler)."""
    if st.session_state.get("auto_refresh"):
        st.rerun(scope="app")


st.sidebar.toggle("🔄 Otomatik yenile (60 sn)", key="auto_refresh")
_auto_refresh_tick()
st.sidebar.caption(
    "Veri: Binance + Yahoo Finance + CFTC · Haber: RSS + FinBERT\n\n"
    "Yatirim tavsiyesi degildir."
)
