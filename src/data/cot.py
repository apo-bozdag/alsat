"""CFTC COT (Commitments of Traders) — buyuk speku oyuncularin net pozisyonu.

Her sali verisi cuma aksami aciklanir; "non-commercial" (fon/speku) long-short
farki, kurumsal paranin yonunu gosterir. Net pozisyonun 4 haftalik degisimi
fiyattan once donen erken sinyal sayilir. Resmi CFTC Socrata API, ucretsiz.
"""
import requests

_API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

MARKETS_COT = {
    "GOLD - COMMODITY EXCHANGE INC.": "Altin",
    "BITCOIN - CHICAGO MERCANTILE EXCHANGE": "Bitcoin (CME)",
    "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE": "S&P 500",
    # DXY guncel CFTC setinde yok; Euro FX dolarin ters vekili olarak izlenir
    "EURO FX - CHICAGO MERCANTILE EXCHANGE": "Euro (dolar tersi)",
}


def fetch_cot() -> list[dict]:
    """Takip edilen piyasalarin son net pozisyonu + 4 haftalik degisim."""
    names = ",".join(f"'{n}'" for n in MARKETS_COT)
    resp = requests.get(
        _API,
        params={
            "$select": "market_and_exchange_names,report_date_as_yyyy_mm_dd,"
                       "noncomm_positions_long_all,noncomm_positions_short_all",
            "$where": f"market_and_exchange_names in({names})",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 80,  # piyasa basina bol pay (raporlar ayni gunde kesismeyebiliyor)
        },
        timeout=15,
    )
    resp.raise_for_status()

    by_market: dict[str, list[dict]] = {}
    for row in resp.json():
        by_market.setdefault(row["market_and_exchange_names"], []).append(row)

    out = []
    for name, rows in by_market.items():
        rows.sort(key=lambda r: r["report_date_as_yyyy_mm_dd"], reverse=True)
        nets = [
            int(r["noncomm_positions_long_all"]) - int(r["noncomm_positions_short_all"])
            for r in rows
        ]
        net = nets[0]
        change_4w = net - nets[4] if len(nets) > 4 else None
        if net > 0:
            stance = "long agirlikli"
        elif net < 0:
            stance = "short agirlikli"
        else:
            stance = "dengede"
        trend = ""
        if change_4w is not None:
            trend = "↑ artiyor" if change_4w > 0 else "↓ azaliyor" if change_4w < 0 else "→ sabit"
        out.append(
            {
                "Piyasa": MARKETS_COT[name],
                "Net Pozisyon": net,
                "4 Hafta Degisim": change_4w,
                "Durum": f"{stance} {trend}".strip(),
                "Rapor": rows[0]["report_date_as_yyyy_mm_dd"][:10],
            }
        )
    return sorted(out, key=lambda r: r["Piyasa"])
