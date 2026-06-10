"""Ekonomik takvim: piyasayi oynatan ABD veri/karar gunleri.

Profesyonel kural: FOMC karari ve buyuk veri aciklamasi oncesi yeni pozisyon
acilmaz, stoplar sikilir — aciklama ani her iki yonde sert hareket uretir.

Kaynak durumu: BLS/FRED API'leri key'siz erisime kapali (403). Bu yuzden:
- FOMC: Fed'in yillik yayimladigi KESIN tarihler (karar gunu, ikinci gun)
- NFP (tarim disi istihdam): kural geregi ayin ilk cumasi — hesaplanir
CPI gibi degisken tarihli olaylar bilerek dahil edilmedi (yanlis tarih
gostermek hic gostermemekten kotu). Yeni yil geldiginde FOMC listesi
guncellenmeli.
"""
from datetime import date, timedelta

# Fed'in yayimladigi 2026 FOMC toplantilari — karar aciklamasi 2. gun yapilir
FOMC_DECISIONS = [
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29), date(2026, 6, 17),
    date(2026, 7, 29), date(2026, 9, 16), date(2026, 10, 28), date(2026, 12, 9),
]

WARN_DAYS = 2  # olaydan kac gun once uyari gosterilsin


def _first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def upcoming_events(today: date | None = None, days_ahead: int = 14) -> list[dict]:
    """Onumuzdeki N gunun onemli olaylari (yakindan uzaga sirali)."""
    today = today or date.today()
    horizon = today + timedelta(days=days_ahead)
    events = []
    for d in FOMC_DECISIONS:
        if today <= d <= horizon:
            events.append({"date": d, "name": "FOMC faiz karari", "impact": "yuksek"})
    for month_shift in (0, 1):
        m = today.month + month_shift
        y = today.year + (m - 1) // 12
        nfp = _first_friday(y, (m - 1) % 12 + 1)
        if today <= nfp <= horizon:
            events.append({"date": nfp, "name": "ABD istihdam verisi (NFP)", "impact": "yuksek"})
    return sorted(events, key=lambda e: e["date"])


def imminent_warning(today: date | None = None) -> str | None:
    """Olay WARN_DAYS icindeyse sinyal panelinde gosterilecek uyari metni."""
    today = today or date.today()
    for event in upcoming_events(today, days_ahead=WARN_DAYS):
        days = (event["date"] - today).days
        when = "BUGUN" if days == 0 else ("yarin" if days == 1 else f"{days} gun sonra")
        return (
            f"📅 {event['name']} {when} ({event['date'].strftime('%d.%m.%Y')}) — "
            "aciklama oncesi yeni pozisyon acmak riskli, mevcut stoplari gozden gecir."
        )
    return None
