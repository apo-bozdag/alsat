"""🌍 Genel Bakis — acilis sayfasi: kus bakisi, sakin dunya gorunumu.

Hicbir secim gerektirmez. Akis: dunyanin durumu -> tum piyasalarda sinyal
tablosu (satira tiklayinca Analiz'e gider) -> dagilim onerisi -> buyuk
oyuncular -> karsilastirmali seyir.
"""
import pandas as pd
import streamlit as st

from src.data import econcal, panorama
from src.portfolio import allocator
from src.ui import chart, shared


@st.cache_data(ttl=3600, show_spinner="Tum sepet simule ediliyor (1-2 dk)...")
def _cached_portfolio_backtest(start_iso: str, end_iso: str, capital: float) -> dict:
    from datetime import datetime

    from src.signals.portfolio_backtest import run_portfolio_backtest

    return run_portfolio_backtest(
        datetime.fromisoformat(start_iso), datetime.fromisoformat(end_iso), capital
    )


def page() -> None:
    st.title("🌍 Genel Bakis")
    st.caption("Dunya nerede, para nereye akiyor? — secim gerektirmeyen kus bakisi.")

    bundle = shared.news_bundle()
    capital = st.session_state.get("capital_input", allocator.load_capital())

    # ── Ust serit: 6 gosterge ────────────────────────────────────────────
    g1, g2, g3, g4, g5, g6 = st.columns(6)
    fng = shared.cached_fear_greed()
    if fng:
        g1.metric("Kripto Korku & Hirs", f"{fng['value']}", fng["label"], delta_color="off")
    vix = shared.cached_vix()
    if vix:
        g2.metric("VIX (borsa korkusu)", f"{vix['value']:.1f}", vix["label"], delta_color="off")
    cg = shared.cached_crypto_global()
    if cg:
        g3.metric("BTC Dominansi", f"%{cg['btc_dominance']:.1f}",
                  "riskten kacis gostergesi", delta_color="off")
        g4.metric("Stablecoin (USDT) Payi", f"%{cg['usdt_share']:.1f}",
                  "kenarda bekleyen para", delta_color="off")
    g5.metric("Makro Haber Ortami", f"{bundle['macro']:+.2f}",
              "pozitif" if bundle["macro"] > 0.1 else "negatif" if bundle["macro"] < -0.1 else "notr",
              delta_color="off")
    g6.metric("Jeopolitik Risk", f"{bundle['geo']:+.2f}",
              "🚨 yuksek gerilim" if bundle["geo"] < -0.5 else "sakin", delta_color="off")

    # Jeopolitik manset + yaklasan olaylar yan yana
    left, right = st.columns(2)
    geo_items = [n for n in bundle["scored"] if n.get("geopolitical")][:4]
    if geo_items:
        with left:
            st.markdown("##### 🚨 Jeopolitik gundem")
            for item in geo_items:
                st.markdown(
                    f"<small>• [{item['title']}]({item['link']}) — {item['source']}</small>",
                    unsafe_allow_html=True,
                )
    events = econcal.upcoming_events()
    if events:
        with right:
            st.markdown("##### 📅 Yaklasan olaylar (14 gun)")
            for e in events:
                st.markdown(
                    f"<small>• **{e['date'].strftime('%d.%m %a')}** — {e['name']}</small>",
                    unsafe_allow_html=True,
                )
            st.caption("Kural: aciklama oncesi yeni pozisyon acilmaz, stoplar sikilir.")

    st.divider()

    # ── Sinyal tablosu (tiklanabilir) ────────────────────────────────────
    st.markdown("##### Tum piyasalarda sinyal durumu — satira tikla, analize git")
    with st.spinner("Tum piyasalar taraniyor (ilk seferde ~30 sn)..."):
        rows = shared.overview_rows(bundle)
    table = pd.DataFrame(rows)
    event = st.dataframe(
        table.drop(columns=["_symbol", "_market"]),
        width="stretch", hide_index=True, height=420,
        on_select="rerun", selection_mode="single-row", key="overview_table",
    )
    if event.selection.rows:
        picked = rows[event.selection.rows[0]]
        shared.goto_analysis(picked["_market"], picked["_symbol"])

    # ── Dagilim onerisi ──────────────────────────────────────────────────
    st.markdown("##### 💰 Dagilim onerisi — paranin yuzde kaci nerede durmali?")
    alloc = allocator.suggest_allocation(rows, capital)
    if not alloc["rows"]:
        st.info(alloc.get("note") or "AL sinyali yok.")
    else:
        a1, a2 = st.columns([3, 1])
        a1.dataframe(
            pd.DataFrame(alloc["rows"]),
            column_config={
                "Oneri %": st.column_config.NumberColumn(format="%.1f%%"),
                "Tutar": st.column_config.NumberColumn(format="$%.0f"),
            },
            width="stretch", hide_index=True,
        )
        a2.metric("Nakit / Stablecoin", f"%{alloc['cash_pct']:.1f}",
                  f"${capital * alloc['cash_pct'] / 100:,.0f}", delta_color="off")
        if alloc.get("note"):
            st.warning(alloc["note"])
        st.caption(
            "Kural seti: yalniz AL sinyalli varliklar, skorla oranli pay; tek varlik "
            "max %15, tek piyasa max %50 (korelasyon tavani); kalani nakit. "
            "Yatirim tavsiyesi degildir."
        )

    # ── Buyuk oyuncular (COT) ────────────────────────────────────────────
    st.markdown("##### 🏦 Buyuk Oyuncular (CFTC COT — haftalik)")
    try:
        st.dataframe(
            pd.DataFrame(shared.cached_cot()),
            column_config={
                "Net Pozisyon": st.column_config.NumberColumn(format="%d"),
                "4 Hafta Degisim": st.column_config.NumberColumn(format="%+d"),
            },
            width="stretch", hide_index=True,
        )
        st.caption(
            "Non-commercial (fon/speku) long − short kontrat farki. Pozitif = "
            "kurumsal para yukari oynuyor; 4 haftalik degisim yonu erken sinyaldir."
        )
    except Exception as exc:
        st.warning(f"COT verisi alinamadi: {exc}")

    # ── Portfoy backtest ─────────────────────────────────────────────────
    with st.expander("🧪 Portfoy Backtest — dagilim kurallariyla tum sepet gecmiste ne yapardi?"):
        st.caption(
            "Tum varliklar gunluk dilimde, canli paneldeki kurallarla: kirilim "
            "girisi, %15 varlik / %50 piyasa tavani, uyarlanan trailing cikis, "
            "bos para nakitte. Yurutme gunluk kapanislarla — 31 varligin "
            "verisi cekildigi icin ilk calistirma 1-2 dk surer."
        )
        from datetime import date as _date, datetime as _dt, timedelta as _td

        pb1, pb2, pb3 = st.columns([1, 1, 1])
        pb_start = pb1.date_input("Baslangic", value=_date.today() - _td(days=730),
                                  key="pb_start")
        pb_end = pb2.date_input("Bitis", value=_date.today(), key="pb_end")
        if pb3.button("Calistir", key="pb_run") and pb_start < pb_end:
            result = _cached_portfolio_backtest(
                pb_start.isoformat(), pb_end.isoformat(), capital
            )
            if "error" in result:
                st.error(result["error"])
            else:
                r1, r2, r3, r4, r5 = st.columns(5)
                r1.metric("Son deger", f"${result['final_equity']:,.0f}")
                r2.metric("Getiri", f"%{result['total_return_pct']:+.1f}")
                r3.metric("Max dusus", f"%{result['max_drawdown_pct']:.1f}")
                r4.metric("Islem", result["n_trades"])
                r5.metric("Isabet", f"%{result['win_rate']:.0f}")
                st.line_chart(result["curve"], y="equity", height=260)
                if result["n_trades"]:
                    st.dataframe(result["trades"].tail(25), width="stretch",
                                 hide_index=True)

    # ── Karsilastirmali seyir ────────────────────────────────────────────
    st.markdown("##### Varliklarin karsilastirmali seyri")
    period = st.radio(
        "Donem", list(panorama.PERIODS), index=2, horizontal=True,
        label_visibility="collapsed",
    )
    try:
        pano_table, normalized = panorama.build_view(
            shared.cached_panorama_history(), panorama.PERIODS[period]
        )
        st.caption(
            f"Tum varliklar {period.lower()} once 100 kabul edildi — cizgisi 100'un "
            "ustunde olan kazandiriyor, egim yonu artis/azalisi gosterir."
        )
        st.plotly_chart(chart.build_panorama_chart(normalized), width="stretch")
        st.dataframe(
            pano_table,
            column_config={
                "Fiyat": st.column_config.NumberColumn(format="%.2f"),
                "Getiri %": st.column_config.NumberColumn(format="%+.2f%%"),
                "Trend": st.column_config.LineChartColumn(f"Seyir ({period.lower()})"),
            },
            width="stretch", hide_index=True,
        )
    except Exception as exc:
        st.error(f"Panorama verisi cekilemedi: {exc}")
