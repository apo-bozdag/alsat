"""Pozisyon boyutu (%1-2 kurali) ve basit portfoy dagilim onerisi.

Profesyonel standart: tek islemde sermayenin %1-2'sinden fazlasi riske
atilmaz. Pozisyon buyuklugu stop mesafesinden turetilir — stop genisse
pozisyon kucuk, stop darsa buyuk olur; kayip her durumda ayni kalir.
"""
import json
from pathlib import Path

_STORE = Path(__file__).resolve().parents[2] / ".portfolio.json"

# Dagilim onerisi sinirlari: tek varlik ve tek piyasa tavani asiri
# yogunlasmayi engeller (korelasyon riski).
MAX_PER_ASSET = 0.15
MAX_PER_MARKET = 0.50


def load_capital(default: float = 10_000.0) -> float:
    try:
        return float(json.loads(_STORE.read_text())["capital"])
    except Exception:
        return default


def save_capital(capital: float) -> None:
    _STORE.write_text(json.dumps({"capital": capital}))


def position_size(capital: float, risk_pct: float, entry: float, stop: float) -> dict | None:
    """%X kuralina gore pozisyon: adet, tutar, sermaye orani.

    risk_pct: 0.01 => sermayenin %1'i riske edilir.
    """
    per_unit_risk = entry - stop
    if per_unit_risk <= 0 or entry <= 0 or capital <= 0:
        return None
    risk_amount = capital * risk_pct
    qty = risk_amount / per_unit_risk
    value = qty * entry
    capped = value > capital
    if capped:  # kaldiracsiz hesap: pozisyon sermayeyi asamaz
        value = capital
        qty = value / entry
        risk_amount = qty * per_unit_risk
    return {
        "qty": qty,
        "value": value,
        "pct_of_capital": value / capital * 100,
        "risk_amount": risk_amount,
        "capped": capped,
    }


def suggest_allocation(overview_rows: list[dict], capital: float) -> dict:
    """Genel Bakis tablosundan basit dagilim onerisi.

    Kural seti (bilincli olarak basit — kara kutu degil):
    - Yalniz AL sinyali olan varliklar pay alir, skorlariyla oranli.
    - Tek varlik en fazla %15, tek piyasa en fazla %50 (korelasyon tavani).
    - Kalan her sey nakit/stablecoin onerisidir; hic AL yoksa %100 nakit.
    """
    candidates = [r for r in overview_rows if "AL" in r["Sinyal"] and r["Skor"] > 0]
    if not candidates:
        return {"rows": [], "cash_pct": 100.0, "note": "Hicbir piyasada AL sinyali yok — kenarda beklemek de pozisyondur."}

    total_score = sum(r["Skor"] for r in candidates)
    raw = [
        {**r, "weight": min(r["Skor"] / total_score, MAX_PER_ASSET)}
        for r in candidates
    ]

    # Piyasa tavani: ayni piyasadaki agirliklar toplami siniri asarsa olcekle
    by_market: dict[str, float] = {}
    for r in raw:
        by_market[r["Piyasa"]] = by_market.get(r["Piyasa"], 0.0) + r["weight"]
    for r in raw:
        market_total = by_market[r["Piyasa"]]
        if market_total > MAX_PER_MARKET:
            r["weight"] *= MAX_PER_MARKET / market_total

    rows = [
        {
            "Piyasa": r["Piyasa"],
            "Varlik": r["Varlik"],
            "Skor": r["Skor"],
            "Oneri %": round(r["weight"] * 100, 1),
            "Tutar": round(r["weight"] * capital, 0),
        }
        for r in sorted(raw, key=lambda x: -x["weight"])
    ]
    invested = sum(r["Oneri %"] for r in rows)
    note = None
    crypto_count = sum(1 for r in rows if "Kripto" in r["Piyasa"])
    if crypto_count >= 3:
        note = ("Dikkat: onerideki kripto varliklar yuksek korelasyonlu — "
                "uclu kripto pozisyonu pratikte tek buyuk pozisyon gibi davranir.")
    return {"rows": rows, "cash_pct": round(100 - invested, 1), "note": note}
