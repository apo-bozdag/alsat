"""Opsiyonel derin haber analizi — yerel Ollama LLM ile.

Ollama servisi calismiyorsa uygulama FinBERT ile devam eder; bu modul
sadece analiz butonlarina basildiginda devreye girer.
"""
from src.config import OLLAMA_MODELS


def is_available() -> bool:
    return pick_model() is not None


def pick_model() -> str | None:
    """Tercih listesinden kurulu olan ilk modeli secer."""
    try:
        import ollama

        installed = {m.model for m in ollama.list().models}
        for name in OLLAMA_MODELS:
            if any(i == name or i.startswith(name) for i in installed):
                return name
        # tercih listesinde yoksa kurulu herhangi birini kullan
        return next(iter(installed), None)
    except Exception:
        return None


def market_commentary(context: str, model: str | None = None) -> str:
    """Dashboard'daki TUM verilerden (skor, rejim, turev, haber, panorama)
    butuncul bir Turkce piyasa yorumu uretir."""
    import ollama

    model = model or pick_model()

    prompt = (
        "Sen tecrubeli bir piyasa analistisin. Asagida bir kripto sinyal "
        "panosunun guncel tum verileri var. Bu verilerin TAMAMINI birlikte "
        "degerlendirip Turkce, net ve kisa bir yorum yaz (en fazla 150 kelime):\n\n"
        f"{context}\n\n"
        "Yorumunda sunlara degin:\n"
        "1. Buyuk resim: rejim + makro ortam + jeopolitik durum ne soyluyor?\n"
        "2. Bu coin ozelinde skor bilesenleri arasinda celiski var mi? "
        "(orn. teknik pozitif ama haber negatif)\n"
        "3. Panoramaya gore para hangi varliklara akiyor, kripto bundan nasil etkilenir?\n"
        "4. Tek cumlelik sonuc: simdi ne yapmak mantikli (al/bekle/sat ve neden).\n"
        "Madde isareti kullanma, akici paragraf yaz. Abartili kesinlikten kacin."
    )
    response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]


def deep_analyze(coin_name: str, headlines: list[dict], model: str | None = None) -> str:
    """Secili coin'in son haberlerini yerel LLM'e yorumlatir (Turkce)."""
    import ollama

    model = model or pick_model()

    news_block = "\n".join(
        f"- [{h['sentiment']}] {h['title']} ({h['source']})" for h in headlines
    )
    prompt = (
        f"Sen bir kripto piyasa analistisin. Asagida {coin_name} ile ilgili "
        f"guncel haber basliklari ve FinBERT sentiment etiketleri var:\n\n"
        f"{news_block}\n\n"
        f"Turkce olarak kisa ve net cevapla:\n"
        f"1. Bu haberlerin {coin_name} fiyatina olasi etkisi (olumlu/olumsuz/notr) ve nedeni\n"
        f"2. Erken sinyal niteliginde bir gelisme var mi?\n"
        f"3. Kisa vade (1-3 gun) beklentin tek cumleyle\n"
        f"Yatirim tavsiyesi olmadigini belirtmene gerek yok, analiz yeterli."
    )
    response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]
