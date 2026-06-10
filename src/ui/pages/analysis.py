"""📊 Analiz — varlik secimi + sinyal + grafik + pozisyon + backtest."""
from datetime import date, timedelta

import streamlit as st

from src.config import ALL_ASSETS, MARKETS, REGIME_MAP
from src.data import econcal, panorama
from src.portfolio import alarms, allocator
from src.sentiment import llm as llm_module
from src.signals import engine
from src.ui import chart, shared, sidebar


@st.cache_data(ttl=300, show_spinner=False)
def _cached_commentary(context: str) -> str:
    return llm_module.market_commentary(context)


def page() -> None:
    # Genel Bakis'tan tiklanip gelindiyse secimleri devral
    if "goto_market" in st.session_state:
        st.session_state["market_select"] = st.session_state.pop("goto_market")
    if "goto_symbol" in st.session_state:
        target = st.session_state.pop("goto_symbol")
        market_name = st.session_state.get("market_select", list(MARKETS)[0])
        st.session_state[f"asset_{market_name}"] = target

    market_name = sidebar.select_market()
    market = MARKETS[market_name]
    provider = market["provider"]
    bundle = shared.news_bundle()

    try:
        tickers = shared.cached_tickers(market_name)
    except Exception as exc:
        st.error(f"Veri kaynagina ulasilamadi: {exc}")
        st.stop()

    # Sidebar rozetleri
    badge_tf = st.session_state.get(f"tf_{market_name}", market["default_tf"])
    actions = {}
    for sym in market["assets"]:
        try:
            df_sym = shared.analyzed(provider, sym, badge_tf)
            actions[sym] = engine.current_recommendation(
                df_sym, shared.build_extras(provider, sym, df_sym, bundle)
            )["action"]
        except Exception:
            actions[sym] = ""

    fng_display = shared.cached_fear_greed() if provider == "binance" else None
    symbol, interval = sidebar.render(market_name, tickers, actions, fng_display)
    capital = st.session_state.get("capital_input", allocator.load_capital())
    risk_pct = st.session_state.get("risk_input", 1.0) / 100

    # ── Secili varlik analizi ───────────────────────────────────────────
    df = shared.analyzed(provider, symbol, interval)
    if df.empty:
        st.error("Bu varlik icin veri alinamadi.")
        st.stop()
    extras = shared.build_extras(provider, symbol, df, bundle)
    rec = engine.current_recommendation(df, extras)
    meta = ALL_ASSETS[symbol]

    action_color = {"AL": "🟢", "SAT": "🔴", "BEKLE": "⚪"}[rec["action"]]
    regime_label = {1: "🐂 Yukselis", 0: "➖ Notr", -1: "🐻 Dusus"}[rec["regime"]]
    change = tickers.get(symbol, {}).get("change_pct")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(meta["name"], shared.fmt_price(rec["price"], provider),
              f"{change:+.2f}% (gunluk)" if change is not None else None)
    c2.metric("Sinyal", f"{action_color} {rec['action']}", f"erken skor {rec['score']:+.2f}")
    c3.metric("Piyasa Rejimi", regime_label,
              f"ust dilim: {REGIME_MAP.get(interval) or '—'}", delta_color="off")
    c4.metric("Trailing Stop (uyarlanir)", shared.fmt_price(rec["stop"], provider))
    c5.metric("Kirilim Seviyesi (20)", shared.fmt_price(rec["breakout_level"], provider))

    if rec["regime_gated"]:
        st.warning(
            "Fiyat kirilim bandinin ustunde ama ust zaman dilimi rejimi onaylamiyor — "
            "trende karsi islem riskli oldugu icin BEKLE'ye cekildi."
        )
    event_warning = econcal.imminent_warning()
    if event_warning:
        st.warning(event_warning)

    # Pozisyon hesaplayici
    pos = allocator.position_size(capital, risk_pct, rec["price"], rec["stop"])
    if pos:
        icon = "🟢" if rec["action"] == "AL" else "⚪"
        with st.expander(
            f"{icon} Pozisyon hesaplayici — bu sinyale girilseydi ne kadar alinmali?",
            expanded=(rec["action"] == "AL"),
        ):
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Onerilen miktar", f"{pos['qty']:,.4f} adet")
            p2.metric("Pozisyon tutari", f"${pos['value']:,.0f}",
                      f"sermayenin %{pos['pct_of_capital']:.1f}'i", delta_color="off")
            p3.metric("Riske edilen", f"${pos['risk_amount']:,.0f}",
                      f"%{risk_pct * 100:.1f} kurali", delta_color="off")
            p4.metric("Stop seviyesi", shared.fmt_price(rec["stop"], provider))
            if pos["capped"]:
                st.caption("⚠️ Stop cok dar — pozisyon kaldiracsiz tavana (%100) cekildi.")
            if rec["action"] != "AL":
                st.caption("Su an AL sinyali yok — bu hesap bilgi amacli.")
        st.session_state["last_calc"] = {
            "symbol": symbol, "entry": rec["price"], "stop": rec["stop"], "qty": pos["qty"],
        }

    # Skor dagilimi
    with st.expander("Skor dagilimi — sinyal neden boyle? (11 bilesen)"):
        labels = {
            "trend": "Trend (EMA)", "rsi": "RSI", "macd": "MACD", "volume": "Hacim",
            "news": "Haber", "macro": "Makro Haber", "geo": "Jeopolitik 🚨",
            "funding": "Funding", "lsr": "Long/Short", "taker": "Taker Akisi",
            "fng": "Korku/Hirs",
        }
        items = list(rec["breakdown"].items())
        for row_items in (items[:6], items[6:]):
            cols = st.columns(6)
            for col, (key, val) in zip(cols, row_items):
                col.metric(labels[key], f"{val:+.2f}")
        st.caption(
            "Fiyat bilesenleri (ilk 4) grafikteki gecmis isaretleri de uretir; erken "
            "sinyal bilesenleri yalnizca guncel oneriye eklenir. Funding/Long-Short/"
            "Taker/Korku-Hirs yalniz kripto icin mevcut."
        )

    # AI genel yorum
    with st.expander("🧠 Genel Yorum — tum verileri bilen yerel AI sentezi"):
        if not llm_module.is_available():
            st.warning("Ollama servisi calismiyor — `ollama serve` ile baslat.")
        elif st.button("Yorum uret", key="commentary_btn"):
            with st.spinner("Yerel model tum verileri degerlendiriyor (~15-30 sn)..."):
                try:
                    st.markdown(_cached_commentary(
                        _commentary_context(market_name, symbol, interval, rec,
                                            change, bundle)
                    ))
                    st.caption(f"Yerel {llm_module.pick_model()} uretimi — yatirim tavsiyesi degildir.")
                except Exception as exc:
                    st.error(f"Yorum uretilemedi: {exc}")

    # Fiyat alarmi
    with st.expander("🔔 Fiyat alarmi — seviye gecilince Telegram'a haber ver"):
        al1, al2 = st.columns([2, 1])
        level = al1.number_input(
            "Seviye", value=float(rec["breakout_level"] or rec["price"]),
            format="%.4f", key=f"alarm_level_{symbol}",
            help="Varsayilan: kirilim seviyesi. Fiyat bu seviyeyi gecince mesaj gelir.",
        )
        if al2.button("Alarm kur", key=f"alarm_btn_{symbol}"):
            a = alarms.add(symbol, level, rec["price"])
            direction = "ustune cikinca" if a["direction"] == "above" else "altina dusunce"
            st.success(f"{meta['short']} {level:,.4f} seviyesinin {direction} Telegram'a bildirilecek.")
        active = [a for a in alarms.list_alarms() if a["symbol"] == symbol]
        for a in active:
            ar1, ar2 = st.columns([4, 1])
            arrow = "⬆️" if a["direction"] == "above" else "⬇️"
            ar1.markdown(f"{arrow} `{a['level']:,.4f}` — kurulma: {a['created_at'][:16]}")
            if ar2.button("Sil", key=f"alarm_del_{a['id']}"):
                alarms.remove(a["id"])
                st.rerun()
        st.caption("Alarmlar tek atimlik: tetiklenince mesaj gider ve alarm silinir. "
                   "Bildirici ~60 sn'de bir kontrol eder.")

    # Grafik + Backtest
    tab_chart, tab_backtest = st.tabs(["📊 Grafik", "🧪 Backtest"])
    with tab_chart:
        st.plotly_chart(
            chart.build_chart(df, f"{meta['name']} · {interval}", rec),
            width="stretch",
        )
    with tab_backtest:
        _backtest_section(provider, symbol, interval, meta)


def _backtest_section(provider: str, symbol: str, interval: str, meta: dict) -> None:
    st.caption(
        "Sectigin tarih araliginda long-only simulasyon: Donchian kirilim girisi, "
        "ust dilim rejim filtresi, oynakliga uyarlanan trailing stop; kripto icin "
        "gecmis Korku&Hirs + funding duygu filtresi. Acik kalan pozisyon son "
        "fiyatla degerlenir. Gecmis gelecegi garanti etmez."
    )
    min_start = date(2017, 8, 17) if provider == "binance" else date(2005, 1, 1)
    bc1, bc2 = st.columns(2)
    bt_start = bc1.date_input(
        "Baslangic", value=date.today() - timedelta(days=730),
        min_value=min_start, max_value=date.today() - timedelta(days=1),
    )
    bt_end = bc2.date_input(
        "Bitis", value=date.today(),
        min_value=min_start + timedelta(days=1), max_value=date.today(),
    )
    if bt_start >= bt_end:
        st.error("Baslangic tarihi bitisten once olmali.")
        return
    result = shared.cached_backtest(provider, symbol, interval,
                                    bt_start.isoformat(), bt_end.isoformat())
    if result["n_trades"] == 0:
        st.info("Bu aralikta tamamlanmis islem yok (rejim filtresi alimlari engellemis olabilir).")
        return
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Islem sayisi", result["n_trades"])
    b2.metric("Isabet orani", f"%{result['win_rate']:.0f}")
    b3.metric("Strateji getirisi", f"%{result['total_return_pct']:+.1f}")
    b4.metric("Al-ve-tut", f"%{result['buy_hold_pct']:+.1f}")
    st.dataframe(result["trades"], width="stretch", hide_index=True)


def _commentary_context(market_name: str, symbol: str, interval: str, rec: dict,
                        change: float | None, bundle: dict) -> str:
    """LLM'e verilecek tam durum ozeti — skor, rejim, gostergeler, haber, panorama."""
    meta = ALL_ASSETS[symbol]
    fng = shared.cached_fear_greed()
    labels = {
        "trend": "Trend(EMA)", "rsi": "RSI", "macd": "MACD", "volume": "Hacim",
        "news": "Haber", "macro": "MakroHaber", "geo": "Jeopolitik",
        "funding": "Funding", "lsr": "Long/Short", "taker": "TakerAkisi",
        "fng": "Korku/Hirs",
    }
    parts = [
        f"VARLIK: {meta['name']} ({market_name}) | Fiyat: {rec['price']:,.2f} | "
        + (f"Gunluk degisim: {change:+.2f}%" if change is not None else ""),
        f"SINYAL: {rec['action']} | Erken sinyal skoru: {rec['score']:+.2f} "
        f"(esikler: AL>=+3, SAT<=-3)",
        f"REJIM ({REGIME_MAP.get(interval) or '-'} ust dilim): "
        + {1: "Yukselis", 0: "Notr", -1: "Dusus"}[rec["regime"]],
        "SKOR BILESENLERI: " + ", ".join(
            f"{labels[k]}={v:+.2f}" for k, v in rec["breakdown"].items()
        ),
        f"KORKU&HIRS ENDEKSI (kripto): {fng['value']} ({fng['label']})" if fng else "",
        f"MAKRO HABER SKORU: {bundle['macro']:+.2f} | JEOPOLITIK RISK: {bundle['geo']:+.2f}",
    ]
    vix = shared.cached_vix()
    cg = shared.cached_crypto_global()
    if vix:
        parts.append(f"VIX: {vix['value']:.1f} ({vix['label']})")
    if cg:
        parts.append(f"BTC DOMINANSI: %{cg['btc_dominance']:.1f} | USDT PAYI: %{cg['usdt_share']:.1f}")
    geo_items = [n for n in bundle["scored"] if n.get("geopolitical")][:5]
    if geo_items:
        parts.append("JEOPOLITIK HABERLER:\n" + "\n".join(f"- {n['title']}" for n in geo_items))
    asset_news = [n for n in bundle["scored"] if symbol in n["coins"]][:5]
    if asset_news:
        parts.append(
            f"{meta['short']} HABERLERI:\n"
            + "\n".join(f"- [{n['sentiment']}] {n['title']}" for n in asset_news)
        )
    try:
        pano_table, _ = panorama.build_view(shared.cached_panorama_history(), 30)
        parts.append(
            "PANORAMA (1 aylik getiri %): "
            + ", ".join(f"{r['Varlik']}: {r['Getiri %']:+.1f}" for _, r in pano_table.iterrows())
        )
    except Exception:
        pass
    return "\n".join(p for p in parts if p)
