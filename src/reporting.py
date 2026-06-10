"""Sabah raporu — her sabah Telegram'a tek mesajlik dunya ozeti.

Icerik: piyasa duygu gostergeleri, gece olan sinyal degisimleri, acik sanal
pozisyonlar, gunun takvim olaylari, sistem karnesi ve (Ollama acaksa) yerel
AI'in 2-3 cumlelik sentezi. Bildirici 09:00'dan sonraki ilk taramada yollar.
"""
from datetime import datetime, timedelta, timezone

from src.config import ALL_ASSETS
from src.data import econcal, news
from src.portfolio import scorecard


def build_morning_report(current_actions: dict[str, str]) -> str:
    now = datetime.now(timezone.utc)
    lines = [f"☀️ *AL-SAT Sabah Raporu* — {datetime.now():%d.%m.%Y}"]

    # Duygu gostergeleri
    fng = news.fetch_fear_greed()
    if fng:
        lines.append(f"😨 Korku & Hirs: *{fng['value']}* ({fng['label']})")

    # Gunun olaylari
    events = econcal.upcoming_events(days_ahead=1)
    for e in events:
        lines.append(f"📅 DIKKAT: bugun/yarin *{e['name']}* ({e['date']:%d.%m})")

    # Son 24 saatin sinyal olaylari
    since = (now - timedelta(hours=24)).isoformat(timespec="minutes")
    overnight = scorecard.events_since(since)
    if overnight:
        lines.append("\n*Son 24 saatte sinyaller:*")
        for e in overnight[-8:]:
            short = ALL_ASSETS.get(e["symbol"], {}).get("short", e["symbol"])
            icon = "🟢" if e["event"] == "AL" else "⚪"
            lines.append(f"{icon} {short}: {e['event']} @ {e['price']:,.4g}")
    else:
        lines.append("\nSon 24 saatte sinyal degisimi yok — sakin gece.")

    # Su an AL'da olan varliklar
    buys = [s for s, a in current_actions.items() if a == "AL"]
    if buys:
        shorts = ", ".join(ALL_ASSETS.get(s, {}).get("short", s) for s in buys)
        lines.append(f"\n🟢 Su an AL sinyalinde: *{shorts}*")
    else:
        lines.append("\n⚪ Su an hicbir varlik AL sinyalinde degil — nakit de pozisyondur.")

    # Sistem karnesi
    st = scorecard.stats()
    if st:
        lines.append(
            f"\n🤖 Sistem karnesi: {st['n']} sanal islem | "
            f"isabet %{st['win_rate']:.0f} | toplam {st['total_ret']:+.1f}%"
        )

    # Yerel AI sentezi (Ollama aciksa)
    synthesis = _ai_synthesis(lines)
    if synthesis:
        lines.append(f"\n🧠 _{synthesis}_")

    return "\n".join(lines)


def _ai_synthesis(report_lines: list[str]) -> str | None:
    """Rapor verisinden 2-3 cumlelik Turkce sentez (Ollama yoksa atlanir)."""
    try:
        from src.sentiment import llm

        model = llm.pick_model()
        if model is None:
            return None
        import ollama

        prompt = (
            "Asagida bir piyasa sabah raporunun ham verileri var. Bunlardan "
            "yatirimciya gunun ruh halini anlatan, abartisiz, 2-3 cumlelik "
            "TURKCE bir sentez yaz. Madde isareti ve baslik kullanma:\n\n"
            + "\n".join(report_lines)
        )
        resp = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
        text = resp["message"]["content"].strip()
        return text if 0 < len(text) < 600 else None
    except Exception:
        return None
