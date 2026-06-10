"""Telegram asistani — hazir komutlar + serbest soruya yerel AI cevabi.

Komutlar canli veriyle aninda cevaplanir; komut olmayan her mesaj icin
bahsedilen varliklar tespit edilir, guncel sinyal/fiyat/rejim baglami
kurulur ve yerel LLM (qwen) Turkce cevap uretir.
"""
import json
from pathlib import Path

from src.config import ALL_ASSETS, MARKETS
from src.data import binance, econcal, news, yahoo

# Sohbet hafizasi: kullanici (chat_id) basina son turlar saklanir ki
# "peki ya ethereum?" gibi takip sorulari baglamini bulsun ve kullanicilarin
# sohbetleri birbirine karismasin. Bildirici her mesaj/cevap ciftini kaydeder.
_HISTORY = Path(__file__).resolve().parents[1] / ".chat_history.json"
_MAX_TURNS = 12          # kullanici basina saklanan toplam mesaj
_CONTEXT_TURNS = 8       # prompt'a verilen son mesaj sayisi


def _all_history() -> dict:
    try:
        data = json.loads(_HISTORY.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _history(chat_id: str) -> list[dict]:
    return _all_history().get(str(chat_id), [])


def remember(chat_id: str, role: str, content: str) -> None:
    data = _all_history()
    hist = data.get(str(chat_id), [])
    hist.append({"role": role, "content": content[:600]})
    data[str(chat_id)] = hist[-_MAX_TURNS:]
    _HISTORY.write_text(json.dumps(data, ensure_ascii=False, indent=1))
from src.indicators.ta import add_indicators
from src.portfolio import alarms, scorecard
from src.sentiment.mapper import map_coins
from src.signals import engine

# kisa ad (kucuk harf) -> sembol
_SHORTS = {meta["short"].lower(): sym for sym, meta in ALL_ASSETS.items()}
_PROVIDERS = {
    sym: mk["provider"] for mk in MARKETS.values() for sym in mk["assets"]
}

HELP = (
    "🤖 *AL-SAT Bot Komutlari*\n"
    "/durum — AL sinyalleri + piyasa ozeti\n"
    "/sinyal BTC — varlik analizi (kisa adiyla)\n"
    "/rapor — sabah raporunu simdi gonder\n"
    "/karne — sistem karnesi\n"
    "/takvim — yaklasan onemli olaylar\n"
    "/alarm BTC 65000 — seviye alarmi kur\n"
    "/alarmlar — kurulu alarmlar\n"
    "/yardim — bu liste\n\n"
    "Komut disinda ne yazarsan yaz — yerel AI guncel verilere bakip cevaplar "
    "(orn. _\"altin almak mantikli mi su an?\"_)"
)


def snapshot(symbol: str) -> dict | None:
    """Varligin guncel tam analizi (fiyat bazli, haber/turev katmani yok)."""
    from src.config import REGIME_MAP

    provider = _PROVIDERS.get(symbol)
    if provider is None:
        return None
    source = yahoo if provider == "yahoo" else binance
    try:
        df = add_indicators(source.get_klines(symbol, "1d"))
        higher_df = source.get_klines(symbol, REGIME_MAP["1d"])
        regime = engine.regime_series(higher_df) if not higher_df.empty else None
        scored = engine.compute_scores(df, regime)
        rec = engine.current_recommendation(scored)
        rec["change_pct"] = float(df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100
        return rec
    except Exception:
        return None


def _fmt(p: float | None) -> str:
    if p is None:
        return "—"
    return f"{p:,.0f}" if p >= 1000 else f"{p:,.2f}" if p >= 1 else f"{p:.4f}"


def _resolve_symbol(word: str) -> str | None:
    return _SHORTS.get(word.lower().strip())


def asset_summary(symbol: str) -> str:
    meta = ALL_ASSETS[symbol]
    rec = snapshot(symbol)
    if rec is None:
        return f"{meta['name']} icin veri alinamadi."
    icon = {"AL": "🟢", "SAT": "🔴", "BEKLE": "⚪"}[rec["action"]]
    regime = {1: "🐂 yukselis", 0: "➖ notr", -1: "🐻 dusus"}[rec["regime"]]
    return (
        f"{icon} *{meta['name']}* — {rec['action']}\n"
        f"Fiyat: {_fmt(rec['price'])} ({rec['change_pct']:+.1f}% gunluk)\n"
        f"Rejim: {regime} | Skor: {rec['score']:+.1f}\n"
        f"Kirilim seviyesi: {_fmt(rec['breakout_level'])}\n"
        f"Trailing stop onerisi: {_fmt(rec['stop'])}"
    )


_SMALLTALK = {
    "naber": "Iyidir, piyasayi izliyorum 👀 Bir varlik sormak istersen yaz, komutlar icin /yardim",
    "selam": "Selam! Sormak istedigin bir varlik var mi? Komutlar icin /yardim",
    "merhaba": "Merhaba! Sormak istedigin bir varlik var mi? Komutlar icin /yardim",
    "sa": "Aleykum selam! Piyasa sorularin icin buradayim.",
    "tesekkurler": "Rica ederim! 📈",
    "tesekkur ederim": "Rica ederim! 📈",
    "eyvallah": "Ne demek 🤝",
    "iyi geceler": "Iyi geceler! Sinyal degisirse haber veririm.",
    "gunaydin": "Gunaydin! Sabah raporu 09:00'dan sonra gelecek; acil bir sey istersen /durum",
}


def handle_text(text: str, current_actions: dict[str, str],
                chat_id: str = "owner", is_owner: bool = True) -> str:
    """Gelen mesaji isler; cevap metni dondurur.

    is_owner=False olan kullanicilar soru sorabilir ve genel komutlari
    kullanabilir; alarm kurma/silme gibi durum degistiren komutlar sahibe ozeldir.
    """
    text = text.strip()
    low = text.lower()

    # Selamlasma/sohbet: LLM'e gitmeden dogal hazir cevap (hizli ve tutarli)
    canned = _SMALLTALK.get(low.rstrip("!?. "))
    if canned:
        return canned

    if low in ("/start", "/yardim", "/help"):
        return HELP

    if low.startswith("/durum"):
        buys = [s for s, a in current_actions.items() if a == "AL"]
        fng = news.fetch_fear_greed()
        lines = ["📊 *Guncel Durum*"]
        if fng:
            lines.append(f"Korku & Hirs: {fng['value']} ({fng['label']})")
        if buys:
            lines.append("🟢 AL sinyalinde: " + ", ".join(
                ALL_ASSETS[s]["short"] for s in buys))
        else:
            lines.append("⚪ Hicbir varlik AL'da degil — nakit de pozisyondur.")
        open_v = scorecard.open_positions()
        if open_v:
            lines.append("Acik sanal pozisyon: " + ", ".join(
                f"{ALL_ASSETS.get(s, {}).get('short', s)} @ {p['entry']:,.4g}"
                for s, p in open_v.items()))
        return "\n".join(lines)

    if low.startswith("/sinyal"):
        parts = text.split()
        if len(parts) < 2:
            return "Kullanim: /sinyal BTC (kisa ad)"
        sym = _resolve_symbol(parts[1])
        if sym is None:
            return f"'{parts[1]}' bulunamadi. Ornek: BTC, ETH, S&P500, ALTIN, THYAO"
        return asset_summary(sym)

    if low.startswith("/rapor"):
        from src.reporting import build_morning_report

        return build_morning_report(current_actions)

    if low.startswith("/karne"):
        st = scorecard.stats()
        if not st:
            return "Henuz tamamlanmis sanal islem yok."
        return (
            f"🤖 *Sistem Karnesi*\n{st['n']} sanal islem | isabet %{st['win_rate']:.0f}\n"
            f"Toplam getiri: {st['total_ret']:+.1f}% | Ortalama islem: {st['avg_ret']:+.1f}%"
        )

    if low.startswith("/takvim"):
        events = econcal.upcoming_events()
        if not events:
            return "Onumuzdeki 14 gunde takvimde onemli olay yok."
        return "📅 *Yaklasan olaylar*\n" + "\n".join(
            f"• {e['date']:%d.%m %a} — {e['name']}" for e in events)

    if low.startswith("/alarm") and not is_owner:
        return "🔒 Alarm komutlari yalnizca bot sahibine acik."

    if low.startswith("/alarmlar"):
        active = alarms.list_alarms()
        if not active:
            return "Kurulu alarm yok. Kurmak icin: /alarm BTC 65000"
        return "🔔 *Kurulu alarmlar*\n" + "\n".join(
            f"• {ALL_ASSETS.get(a['symbol'], {}).get('short', a['symbol'])} "
            f"{'⬆️' if a['direction'] == 'above' else '⬇️'} {a['level']:,.4g}"
            for a in active)

    if low.startswith("/alarm"):
        parts = text.split()
        if len(parts) < 3:
            return "Kullanim: /alarm BTC 65000"
        sym = _resolve_symbol(parts[1])
        if sym is None:
            return f"'{parts[1]}' bulunamadi."
        try:
            level = float(parts[2].replace(",", ""))
        except ValueError:
            return "Seviye sayi olmali. Ornek: /alarm BTC 65000"
        rec = snapshot(sym)
        if rec is None:
            return "Guncel fiyat alinamadi, alarm kurulamadi."
        a = alarms.add(sym, level, rec["price"])
        arrow = "ustune cikinca" if a["direction"] == "above" else "altina dusunce"
        return (f"🔔 Kuruldu: {ALL_ASSETS[sym]['short']} {level:,.4g} "
                f"seviyesinin {arrow} haber verecegim. (su an {_fmt(rec['price'])})")

    if low.startswith("/"):
        return "Bilinmeyen komut. Liste icin /yardim"

    return ai_answer(text, current_actions, chat_id)


def ai_answer(text: str, current_actions: dict[str, str], chat_id: str = "owner") -> str:
    """Serbest soruya canli veri + sohbet gecmisi baglamiyla yerel AI cevabi."""
    from src.sentiment import llm

    model = llm.pick_model()
    if model is None:
        return "Yerel AI su an kapali (Ollama calismiyor). Komutlar icin /yardim"

    history = _history(chat_id)[-_CONTEXT_TURNS:]

    # Soruda gecen varliklar; yoksa gecmis mesajlarda gecenler; yoksa AL'dakiler
    symbols = [s for s in map_coins(text) if s in ALL_ASSETS][:3]
    if not symbols and history:
        past_text = " ".join(h["content"] for h in history if h["role"] == "user")
        symbols = [s for s in map_coins(past_text) if s in ALL_ASSETS][-3:]
    if not symbols:
        symbols = [s for s, a in current_actions.items() if a == "AL"][:3] or ["BTCUSDT"]

    context = []
    fng = news.fetch_fear_greed()
    if fng:
        context.append(f"Kripto Korku&Hirs endeksi: {fng['value']} ({fng['label']})")
    for sym in symbols:
        rec = snapshot(sym)
        if rec:
            meta = ALL_ASSETS[sym]
            regime = {1: "yukselis", 0: "notr", -1: "dusus"}[rec["regime"]]
            context.append(
                f"{meta['name']}: fiyat {_fmt(rec['price'])} ({rec['change_pct']:+.1f}% gunluk), "
                f"sinyal {rec['action']}, rejim {regime}, skor {rec['score']:+.1f}, "
                f"kirilim seviyesi {_fmt(rec['breakout_level'])}, stop {_fmt(rec['stop'])}"
            )
    buys = [ALL_ASSETS[s]["short"] for s, a in current_actions.items() if a == "AL"]
    context.append("Su an AL sinyalindeki varliklar: " + (", ".join(buys) or "yok"))

    import ollama

    system = (
        "Sen AL-SAT adli sinyal panosunun Telegram asistanisin. Kurallarin:\n"
        "0. Selamlasma/sohbet mesajina (naber, selam, tesekkurler...) dogal ve "
        "samimi tek cumleyle karsilik ver; soru sorulmadiysa veri/sinyal dokme.\n"
        "1. SADECE Turkce, en fazla 4 cumle, samimi ama net konus.\n"
        "2. Cevabini asagidaki GUNCEL verilere dayandir; veride olmayani uydurma.\n"
        "3. Sinyal mantigi: AL = kirilim + yukselis rejimi var. SAT = cikis sinyali. "
        "BEKLE = kosullar olusmadi, pozisyona girilmez ama elde varsa stop takip edilir. "
        "'Almak mantikli mi' sorusuna sinyale gore net cevap ver; 'satmak mantikli mi' "
        "sorusunda elde pozisyon varsa stop/rejime gore degerlendir, ikisine birden "
        "'mantikli degil' deme.\n"
        "4. Sen islem YAPAMAZSIN; kullanici senden islem yapmani isterse bunu tek "
        "cumleyle soyle ve hangi kosul olusunca sinyal gelecegini anlat.\n"
        "5. ASLA disclaimer, 'yatirim tavsiyesi degildir', 'profesyonele danisin' "
        "gibi kaliplar yazma. Ayni kelimeyi pes pese tekrarlama.\n\n"
        "Guncel veriler:\n" + "\n".join(f"- {c}" for c in context)
    )
    messages = (
        [{"role": "system", "content": system}]
        + history
        + [{"role": "user", "content": text}]
    )
    resp = ollama.chat(
        model=model,
        messages=messages,
        options={"temperature": 0.3, "num_predict": 400},
    )
    answer = resp["message"]["content"].strip()
    answer = _strip_disclaimer(_strip_foreign(answer))
    # Token limitine takilip yarim kalan son cumleyi at
    if answer and answer[-1] not in ".!?":
        idx = max(answer.rfind("."), answer.rfind("!"), answer.rfind("?"))
        if idx > 40:
            answer = answer[: idx + 1]
    return answer[:3900]


def _strip_foreign(text: str) -> str:
    """Model bazen Cince/Korece karakter sizdiriyor — ilk CJK'dan itibaren kes."""
    for i, ch in enumerate(text):
        if "一" <= ch <= "鿿" or "　" <= ch <= "ヿ" or "가" <= ch <= "힯":
            cut = text[:i].strip()
            return cut if len(cut) > 20 else text
    return text


_DISCLAIMER_MARKERS = (
    "yatirim tavsiyesi", "yatırım tavsiyesi", "disclaimer", "disclameri",
    "garanti etmez", "profesyonel danis", "profesyonele danis", "uzmana danis",
)


def _strip_disclaimer(text: str) -> str:
    """Model talimata ragmen disclaimer kalibi eklerse cumle bazinda ayiklar."""
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = [s for s in sentences if not any(m in s.lower() for m in _DISCLAIMER_MARKERS)]
    return " ".join(kept).strip() or text
