"""Haber paneli: basliklar + sentiment rozetleri + opsiyonel Ollama derin analizi."""
import streamlit as st

from src.config import ALL_ASSETS, OLLAMA_MODELS
from src.sentiment import llm

_BADGE = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}


def render(scored_news: list[dict], selected_symbol: str, macro_score: float = 0.0) -> None:
    st.subheader("📰 Haber Akisi ve Erken Sinyaller")

    macro_emoji = "🟢" if macro_score > 0.1 else "🔴" if macro_score < -0.1 else "⚪"
    st.caption(
        f"Makro ortam skoru: {macro_emoji} {macro_score:+.2f} — genel ekonomi/"
        f"jeopolitik haberlerin agirlikli net sentimenti (tum coinleri etkiler)."
    )

    # Jeopolitik risk haberleri her filtreden once, sabit ustte
    geo_items = [n for n in scored_news if n.get("geopolitical")]
    if geo_items:
        with st.expander(f"🚨 Jeopolitik risk haberleri ({len(geo_items)})", expanded=True):
            for item in geo_items[:8]:
                age = item["published"].strftime("%d %b %H:%M")
                st.markdown(
                    f"🚨 [{item['title']}]({item['link']})  \n"
                    f"<small>{item['source']} · {age} UTC</small>",
                    unsafe_allow_html=True,
                )

    filter_mode = st.radio(
        "Haber filtresi",
        ["Hepsi", f"Sadece {ALL_ASSETS[selected_symbol]['short']}", "Kripto",
         "Makro/Dunya", "🇹🇷 Turkiye"],
        horizontal=True, label_visibility="collapsed",
    )
    if filter_mode == "Hepsi":
        items = scored_news
    elif filter_mode == "Kripto":
        items = [n for n in scored_news if n["category"] == "crypto"]
    elif filter_mode == "Makro/Dunya":
        items = [n for n in scored_news if n["category"] == "macro" and n.get("lang") == "en"]
    elif filter_mode == "🇹🇷 Turkiye":
        items = [n for n in scored_news if n.get("lang") == "tr"]
    else:
        items = [n for n in scored_news if selected_symbol in n["coins"]]

    if not items:
        st.info("Bu filtreyle gosterilecek haber yok.")
    for item in items[:40]:
        badge = "🚨" if item.get("geopolitical") else _BADGE.get(item["sentiment"], "⚪")
        cat = "🇹🇷" if item.get("lang") == "tr" else "🌍" if item["category"] == "macro" else "🪙"
        tags = " ".join(f"`{ALL_ASSETS[s]["short"]}`" for s in item["coins"]) or "`genel`"
        age = item["published"].strftime("%d %b %H:%M")
        st.markdown(
            f"{badge} {cat} [{item['title']}]({item['link']})  \n"
            f"<small>{item['source']} · {age} UTC · guven {item['confidence']:.0%} · {tags}</small>",
            unsafe_allow_html=True,
        )

    _render_deep_analysis(scored_news, selected_symbol)


def _render_deep_analysis(scored_news: list[dict], symbol: str) -> None:
    """Ollama varsa secili coin haberlerini yerel LLM'e yorumlatma bolumu."""
    st.divider()
    coin_name = ALL_ASSETS[symbol]["name"]
    coin_news = [n for n in scored_news if symbol in n["coins"]][:10]

    with st.expander(f"🤖 {coin_name} icin derin analiz (yerel LLM — Ollama)"):
        if not coin_news:
            st.info(f"{coin_name} ile ilgili guncel haber bulunamadi.")
            return
        model = llm.pick_model()
        if model is None:
            st.warning(
                "Ollama servisi calismiyor. Baslatmak icin terminalde: "
                "`ollama serve` ve modeli indirmek icin "
                f"`ollama pull {OLLAMA_MODELS[0]}`. Uygulama FinBERT ile calismaya devam ediyor."
            )
            return
        if st.button("Analiz et", key=f"deep_{symbol}"):
            with st.spinner(f"{model} dusunuyor..."):
                try:
                    st.markdown(llm.deep_analyze(coin_name, coin_news))
                except Exception as exc:
                    st.error(f"Ollama hatasi: {exc}")
