"""Yerel sentiment analizi + varlik bazinda zaman agirlikli skor.

Iki dilli iki model, tamamen yerel:
- Ingilizce: FinBERT (ProsusAI/finbert) — finans haberlerinde egitimli
- Turkce: savasy/bert-base-turkish-sentiment-cased — BloombergHT/Investing TR
Her model ilk kullanimda ~400-450MB iner.
"""
import math
import re
from datetime import datetime, timezone

from src.config import (
    ALL_ASSETS,
    FINBERT_MODEL,
    TURKISH_SENTIMENT_MODEL,
    GEOPOLITICAL_KEYWORDS,
    GEOPOLITICAL_VALUE,
    MACRO_DECAY_HOURS,
    MACRO_WINDOW_HOURS,
    NEWS_DECAY_HOURS,
    NEWS_WINDOW_HOURS,
)

_SIGN = {
    "positive": 1.0, "negative": -1.0, "neutral": 0.0,
    # Turkce model etiket varyantlari
    "label_1": 1.0, "label_0": -1.0, "pozitif": 1.0, "negatif": -1.0,
}
_GEO_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in GEOPOLITICAL_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def load_model():
    """Dil -> pipeline sozlugu yukler. Cagiran taraf st.cache_resource ile sarmali."""
    from transformers import pipeline

    return {
        "en": pipeline("text-classification", model=FINBERT_MODEL),
        "tr": pipeline("text-classification", model=TURKISH_SENTIMENT_MODEL),
    }


def score_news(models, news_items: list[dict]) -> list[dict]:
    """Her habere sentiment etiketi, guven skoru ve ilgili varliklari ekler.

    Haber diline gore uygun model secilir (en -> FinBERT, tr -> Turkce BERT).
    """
    from src.sentiment.mapper import map_coins

    if not news_items:
        return []
    results = [None] * len(news_items)
    for lang, model in models.items():
        idx = [i for i, it in enumerate(news_items) if it.get("lang", "en") == lang]
        if not idx:
            continue
        out = model([news_items[i]["title"] for i in idx], truncation=True)
        for i, res in zip(idx, out):
            results[i] = res

    scored = []
    for item, res in zip(news_items, results):
        if res is None:  # tanimsiz dil — notr birak
            res = {"label": "neutral", "score": 0.0}
        sign = _SIGN.get(res["label"].lower(), 0.0)
        value = sign * float(res["score"])
        sentiment = "positive" if sign > 0 else "negative" if sign < 0 else "neutral"
        # Jeopolitik duzeltme: FinBERT savas haberini notr sayabiliyor
        geopolitical = (
            item["category"] == "macro" and bool(_GEO_PATTERN.search(item["title"]))
        )
        if geopolitical:
            value = min(value, GEOPOLITICAL_VALUE)
            sentiment = "negative"
        scored.append(
            {
                **item,
                "sentiment": sentiment,
                "confidence": float(res["score"]),
                "value": value,
                "geopolitical": geopolitical,
                "coins": map_coins(item["title"]),
            }
        )
    return scored


def aggregate_coin_scores(scored_news: list[dict]) -> dict[str, float]:
    """Varlik basina son 24 saatin zaman agirlikli net sentiment skoru [-1, +1].

    Yeni haber eskisinden daha onemlidir: agirlik exp(-yas/NEWS_DECAY_HOURS)
    ile ussel azalir. Varliga dair haber yoksa skor 0 (notr) kalir.
    Kripto disi varliklar makro kaynaklardaki haberlerden de beslenir.
    """
    now = datetime.now(timezone.utc)
    sums = {symbol: [0.0, 0.0] for symbol in ALL_ASSETS}  # [agirlikli toplam, agirlik]

    for item in scored_news:
        age_hours = (now - item["published"]).total_seconds() / 3600
        if age_hours > NEWS_WINDOW_HOURS:
            continue
        weight = math.exp(-age_hours / NEWS_DECAY_HOURS)
        for symbol in item["coins"]:
            sums[symbol][0] += weight * item["value"]
            sums[symbol][1] += weight

    return {
        symbol: (total / weight if weight > 0 else 0.0)
        for symbol, (total, weight) in sums.items()
    }


def aggregate_macro_score(scored_news: list[dict]) -> float:
    """Genel ekonomi haberlerinin tum piyasaya etkisi [-1, +1].

    Makro haberler coin ayrimi yapmaz: faiz karari, enflasyon gibi gelismeler
    tum riskli varliklari ayni yonde etkiler. Jeopolitik haberler ayri skorda
    (aggregate_geo_score) tutulur ki etkisi panoda ayri gorunsun.
    """
    return _weighted_macro(scored_news, geopolitical=False)


def aggregate_geo_score(scored_news: list[dict]) -> float:
    """Jeopolitik risk haberlerinin (savas/saldiri/yaptirim) net etkisi [-1, 0]."""
    return _weighted_macro(scored_news, geopolitical=True)


def _weighted_macro(scored_news: list[dict], geopolitical: bool) -> float:
    now = datetime.now(timezone.utc)
    total, weight_sum = 0.0, 0.0
    for item in scored_news:
        if item["category"] != "macro" or bool(item.get("geopolitical")) != geopolitical:
            continue
        # Turkce kaynaklar GLOBAL makro skoruna girmez (BIST/TL chatter'i
        # BTC'nin makro bilesenini etkilemesin); varlik eslesmesiyle ilgili
        # varligin kendi haber skorunu zaten besliyorlar.
        if item.get("lang", "en") != "en":
            continue
        age_hours = (now - item["published"]).total_seconds() / 3600
        if age_hours > MACRO_WINDOW_HOURS:
            continue
        weight = math.exp(-age_hours / MACRO_DECAY_HOURS)
        total += weight * item["value"]
        weight_sum += weight
    return total / weight_sum if weight_sum > 0 else 0.0
