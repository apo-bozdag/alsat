"""Haber basligini ilgili varliklarla eslestirir (kelime siniri ile regex arama).

Sadece coinler degil: hisse, emtia, doviz dahil tum MARKETS varliklari.
Boylece "gold" haberi ALTIN sinyalini, "nvidia" haberi NVDA sinyalini besler.
"""
import re

from src.config import ALL_ASSETS

# Her varlik icin derlenmis regex — "sol" kelimesi "solution" ile eslesmesin diye \b
_PATTERNS = {
    symbol: re.compile(
        r"\b(" + "|".join(re.escape(k) for k in meta["keywords"]) + r")\b",
        re.IGNORECASE,
    )
    for symbol, meta in ALL_ASSETS.items()
}


def map_coins(text: str) -> list[str]:
    """Metinde gecen varliklarin sembollerini dondurur (bos liste = genel haber)."""
    return [symbol for symbol, pattern in _PATTERNS.items() if pattern.search(text)]
