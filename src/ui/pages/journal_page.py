"""📒 Islem Gunlugu — pozisyon kayitlari ve performans istatistigi."""
import pandas as pd
import streamlit as st

from src.config import ALL_ASSETS, MARKETS
from src.portfolio import journal, scorecard
from src.ui import shared


def page() -> None:
    st.title("📒 Islem Gunlugu")
    st.caption(
        "Pro kurali: kaydedilmeyen islem, ders alinmayan islemdir. Pozisyon "
        "actiginda buraya isle; kapatinca K/Z ve isabet istatistigin olusur."
    )

    # Analiz sayfasindaki son hesap varsa formu onunla doldur
    last = st.session_state.get("last_calc", {})
    default_symbol = last.get("symbol", "BTCUSDT")

    with st.form("journal_open", clear_on_submit=True):
        st.markdown("**Yeni pozisyon kaydi**")
        j0, j1, j2, j3 = st.columns([1.6, 1, 1, 1])
        symbol = j0.selectbox(
            "Varlik", list(ALL_ASSETS),
            index=list(ALL_ASSETS).index(default_symbol),
            format_func=lambda s: ALL_ASSETS[s]["name"],
        )
        j_entry = j1.number_input("Giris fiyati",
                                  value=float(last.get("entry", 0.0)), format="%.4f")
        j_stop = j2.number_input("Stop", value=float(last.get("stop", 0.0)), format="%.4f")
        j_qty = j3.number_input("Miktar (adet)", min_value=0.0,
                                value=float(last.get("qty", 1.0)), format="%.4f")
        j_note = st.text_input("Not (neden girdin?)",
                               placeholder="orn. kirilim + rejim yukari + haber pozitif")
        if st.form_submit_button("Pozisyonu kaydet"):
            journal.open_position(symbol, ALL_ASSETS[symbol]["name"],
                                  j_entry, j_stop, j_qty, j_note)
            st.success("Kaydedildi.")
            st.rerun()

    # Acik pozisyonlarda canli fiyat icin ticker'lari topla
    live_prices = {}
    open_pos = journal.open_positions()
    if open_pos:
        needed_markets = {
            mk_name for mk_name, mk in MARKETS.items()
            if any(e["symbol"] in mk["assets"] for e in open_pos)
        }
        for mk_name in needed_markets:
            try:
                live_prices.update(shared.cached_tickers(mk_name))
            except Exception:
                pass

        st.markdown("##### Acik pozisyonlar")
        for e in open_pos:
            o1, o2, o3, o4, o5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
            live = live_prices.get(e["symbol"], {}).get("price")
            unrealized = ((live - e["entry"]) * e["qty"]) if live else None
            o1.markdown(
                f"**{e['name']}**  \n<small>{e['opened_at'][:16]} · {e['note'] or '-'}</small>",
                unsafe_allow_html=True,
            )
            o2.metric("Giris", f"{e['entry']:,.4g}", f"{e['qty']:.4g} adet", delta_color="off")
            o3.metric("Stop", f"{e['stop']:,.4g}")
            if unrealized is not None:
                o4.metric("Acik K/Z", f"${unrealized:+,.0f}")
            exit_val = o5.number_input("Cikis fiyati", value=float(live or e["entry"]),
                                       key=f"exit_{e['id']}", format="%.4f",
                                       label_visibility="collapsed")
            if o5.button("Kapat", key=f"close_{e['id']}"):
                journal.close_position(e["id"], exit_val)
                st.rerun()
    else:
        st.info("Acik pozisyon yok.")

    closed = journal.closed_positions()
    if closed:
        st.markdown("##### Kapali islemler")
        jstats = journal.stats()
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Islem", jstats["n"])
        s2.metric("Isabet", f"%{jstats['win_rate']:.0f}")
        s3.metric("Toplam K/Z", f"${jstats['total_pnl']:+,.0f}")
        s4.metric("Ort. getiri", f"%{jstats['avg_pct']:+.1f}")
        st.dataframe(
            pd.DataFrame(closed)[["name", "opened_at", "closed_at", "entry", "exit",
                                  "qty", "pnl", "pnl_pct", "note"]].rename(columns={
                "name": "Varlik", "opened_at": "Acilis", "closed_at": "Kapanis",
                "entry": "Giris", "exit": "Cikis", "qty": "Adet",
                "pnl": "K/Z $", "pnl_pct": "K/Z %", "note": "Not",
            }),
            width="stretch", hide_index=True,
        )

    system_scorecard_section()


def system_scorecard_section() -> None:
    """Sistemin kendi sinyallerinin otomatik karnesi (bildirici besler)."""
    st.divider()
    st.markdown("##### 🤖 Sistem Karnesi — algoritmanin kendi sinyalleri (otomatik)")
    st.caption(
        "Bildirici her AL sinyalinde sanal pozisyon acar, sinyal bitince kapatir. "
        "Backtest'in canli dogrulamasi: algoritma gercekte ne yapiyor? "
        "(30 dk tarama cozunurlugu — kurusu kurusuna degil, yon dogrulugu olcer)"
    )
    open_v = scorecard.open_positions()
    if open_v:
        st.markdown("**Acik sanal pozisyonlar:** " + " · ".join(
            f"`{ALL_ASSETS.get(s, {}).get('short', s)} @ {p['entry']:,.4g}`"
            for s, p in open_v.items()
        ))
    sc_stats = scorecard.stats()
    if sc_stats:
        v1, v2, v3, v4 = st.columns(4)
        v1.metric("Sanal islem", sc_stats["n"])
        v2.metric("Isabet", f"%{sc_stats['win_rate']:.0f}")
        v3.metric("Toplam getiri", f"%{sc_stats['total_ret']:+.1f}")
        v4.metric("Ort. islem", f"%{sc_stats['avg_ret']:+.1f}")
        closed = scorecard.closed_trades()
        st.dataframe(
            pd.DataFrame(closed[-30:]).rename(columns={
                "symbol": "Varlik", "opened_at": "Giris zamani", "closed_at": "Cikis zamani",
                "entry": "Giris", "exit": "Cikis", "ret_pct": "Getiri %",
            }),
            width="stretch", hide_index=True,
        )
    elif not open_v:
        st.info("Henuz sanal islem yok — bildirici calistikca burasi dolacak.")
