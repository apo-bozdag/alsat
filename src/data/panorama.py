"""Piyasa panoramasi: kripto disindaki buyuk varliklarin karsilastirmali seyri.

"Para nereden nereye akiyor?" sorusunun ilk adimi. Veriler yfinance ile
ucretsiz cekilir. Ileride buradaki varliklara sinyal ve rotasyon onerisi
(yuzdesel dagilim) eklenecek.
"""
import pandas as pd

ASSETS = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "BIST 100": "XU100.IS",
    "Dolar/TL": "TRY=X",
    "Altin (ons $)": "GC=F",
    "Gumus (ons $)": "SI=F",
    "Dolar Endeksi (DXY)": "DX-Y.NYB",
    "ABD 10Y Faiz": "^TNX",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
}

PERIODS = {"1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yil": 365}


def fetch_history() -> pd.DataFrame:
    """Tum varliklarin 1 yillik gunluk kapanislari (kolonlar: varlik adi)."""
    import yfinance as yf

    data = yf.download(
        list(ASSETS.values()),
        period="1y",
        interval="1d",
        progress=False,
        auto_adjust=True,
    )["Close"]
    data = data.rename(columns={ticker: name for name, ticker in ASSETS.items()})
    return data.dropna(how="all")


def build_view(history: pd.DataFrame, days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Secilen donem icin (ozet tablo, endekslenmis seri) dondurur.

    Endeksleme: her varlik donem basinda 100 kabul edilir — farkli para
    birimi ve olceklerdeki varliklar ayni grafikte karsilastirilabilir.
    """
    cutoff = history.index.max() - pd.Timedelta(days=days)
    window = history[history.index >= cutoff]

    rows, normalized = [], {}
    for name in window.columns:
        series = window[name].dropna()
        if len(series) < 5:
            continue
        normalized[name] = series / series.iloc[0] * 100
        rows.append(
            {
                "Varlik": name,
                "Fiyat": float(series.iloc[-1]),
                "Getiri %": round(float(series.iloc[-1] / series.iloc[0] - 1) * 100, 2),
                "Trend": [round(float(v), 2) for v in normalized[name].tolist()],
            }
        )
    table = pd.DataFrame(rows).sort_values("Getiri %", ascending=False).reset_index(drop=True)
    return table, pd.DataFrame(normalized)
