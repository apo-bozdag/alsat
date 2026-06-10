"""Uygulama yapilandirmasi: coinler, zaman dilimleri, sinyal ayarlari, haber kaynaklari."""

# ── Takip edilen coinler ──────────────────────────────────────────────
# sembol -> gorunen ad + haber eslestirme anahtar kelimeleri (regex \b ile aranir)
COINS = {
    "BTCUSDT": {"short": "BTC", "name": "Bitcoin", "keywords": ["bitcoin", "btc"]},
    "ETHUSDT": {"short": "ETH", "name": "Ethereum", "keywords": ["ethereum", "eth", "ether"]},
    "SOLUSDT": {"short": "SOL", "name": "Solana", "keywords": ["solana", "sol"]},
    "BNBUSDT": {"short": "BNB", "name": "BNB", "keywords": ["bnb"]},
    "XRPUSDT": {"short": "XRP", "name": "XRP", "keywords": ["xrp", "ripple"]},
    "DOGEUSDT": {"short": "DOGE", "name": "Dogecoin", "keywords": ["dogecoin", "doge"]},
    "AVAXUSDT": {"short": "AVAX", "name": "Avalanche", "keywords": ["avalanche", "avax"]},
    "LINKUSDT": {"short": "LINK", "name": "Chainlink", "keywords": ["chainlink"]},
}

# ── Diger piyasalar (yfinance, ucretsiz) ──────────────────────────────
# Ayni sinyal motoru (rejim + kirilim + trailing) tum varliklara uygulanir.
US_STOCKS = {
    "SPY": {"short": "S&P500", "name": "S&P 500 (SPY)", "keywords": ["s&p 500", "sp500", "wall street"]},
    "QQQ": {"short": "Nasdaq", "name": "Nasdaq 100 (QQQ)", "keywords": ["nasdaq", "tech stocks"]},
    "AAPL": {"short": "AAPL", "name": "Apple", "keywords": ["apple", "iphone"]},
    "MSFT": {"short": "MSFT", "name": "Microsoft", "keywords": ["microsoft"]},
    "NVDA": {"short": "NVDA", "name": "Nvidia", "keywords": ["nvidia"]},
    "TSLA": {"short": "TSLA", "name": "Tesla", "keywords": ["tesla", "musk"]},
    "AMZN": {"short": "AMZN", "name": "Amazon", "keywords": ["amazon"]},
    "GOOGL": {"short": "GOOGL", "name": "Alphabet", "keywords": ["google", "alphabet"]},
    "META": {"short": "META", "name": "Meta", "keywords": ["meta platforms", "facebook"]},
}
BIST_STOCKS = {
    "XU100.IS": {"short": "BIST100", "name": "BIST 100", "keywords": ["bist", "borsa istanbul", "turkish stocks", "bist 100", "borsa"]},
    "THYAO.IS": {"short": "THYAO", "name": "Turk Hava Yollari", "keywords": ["turkish airlines", "thyao", "thy", "türk hava yolları"]},
    "ASELS.IS": {"short": "ASELS", "name": "Aselsan", "keywords": ["aselsan", "asels"]},
    "GARAN.IS": {"short": "GARAN", "name": "Garanti BBVA", "keywords": ["garanti", "garan"]},
    "AKBNK.IS": {"short": "AKBNK", "name": "Akbank", "keywords": ["akbank", "akbnk"]},
    "EREGL.IS": {"short": "EREGL", "name": "Eregli Demir Celik", "keywords": ["erdemir", "eregl", "ereğli"]},
    "TUPRS.IS": {"short": "TUPRS", "name": "Tupras", "keywords": ["tupras", "tuprs", "tüpraş"]},
    "KCHOL.IS": {"short": "KCHOL", "name": "Koc Holding", "keywords": ["koc holding", "kchol", "koç holding"]},
    "BIMAS.IS": {"short": "BIMAS", "name": "BIM Magazalar", "keywords": ["bim", "bimas"]},
    "FROTO.IS": {"short": "FROTO", "name": "Ford Otosan", "keywords": ["ford otosan", "froto"]},
    "TCELL.IS": {"short": "TCELL", "name": "Turkcell", "keywords": ["turkcell", "tcell"]},
    "SAHOL.IS": {"short": "SAHOL", "name": "Sabanci Holding", "keywords": ["sabanci", "sahol"]},
    "ISCTR.IS": {"short": "ISCTR", "name": "Is Bankasi (C)", "keywords": ["is bankasi", "isctr", "iş bankası"]},
    "YKBNK.IS": {"short": "YKBNK", "name": "Yapi Kredi", "keywords": ["yapi kredi", "ykbnk", "yapı kredi"]},
    "SISE.IS": {"short": "SISE", "name": "Sisecam", "keywords": ["sisecam", "sise", "şişecam"]},
    "SASA.IS": {"short": "SASA", "name": "SASA Polyester", "keywords": ["sasa"]},
}
COMMODITIES_FX = {
    "GC=F": {"short": "ALTIN", "name": "Altin (ons $)", "keywords": ["gold", "altın", "altin fiyat", "ons"]},
    "SI=F": {"short": "GUMUS", "name": "Gumus (ons $)", "keywords": ["silver", "gümüş"]},
    "CL=F": {"short": "PETROL", "name": "Ham Petrol (WTI)", "keywords": ["oil", "crude", "opec", "petrol", "brent"]},
    "TRY=X": {"short": "USD/TRY", "name": "Dolar/TL", "keywords": ["lira", "turkish economy", "dolar", "kur", "tcmb", "faiz kararı"]},
    "EURUSD=X": {"short": "EUR/USD", "name": "Euro/Dolar", "keywords": ["euro", "ecb"]},
    "DX-Y.NYB": {"short": "DXY", "name": "Dolar Endeksi", "keywords": ["dollar index"]},
}

MARKETS = {
    "🪙 Kripto": {
        "provider": "binance",
        "assets": COINS,
        "timeframes": ["4h", "1d", "1w", "1M"],
        "default_tf": "1d",
    },
    "🇺🇸 ABD Borsasi": {
        "provider": "yahoo",
        "assets": US_STOCKS,
        "timeframes": ["1d", "1w", "1M"],
        "default_tf": "1d",
    },
    "🇹🇷 BIST": {
        "provider": "yahoo",
        "assets": BIST_STOCKS,
        "timeframes": ["1d", "1w", "1M"],
        "default_tf": "1d",
    },
    "🥇 Emtia & Doviz": {
        "provider": "yahoo",
        "assets": COMMODITIES_FX,
        "timeframes": ["1d", "1w", "1M"],
        "default_tf": "1d",
    },
}
# Haber eslestirme ve skor toplamada kullanilan tum varliklar
ALL_ASSETS = {s: m for mk in MARKETS.values() for s, m in mk["assets"].items()}

# Swing/pozisyon icin anlamli dilimler; 15m-1h gurultusu bilincli olarak yok.
TIMEFRAMES = ["4h", "1d", "1w", "1M"]
DEFAULT_TIMEFRAME = "1d"
KLINE_LIMIT = 500

# Rejim filtresi: secilen dilimin trendi BIR UST dilimde dogrulanir.
# Dusus rejiminde AL, yukselis rejiminde SAT sinyali uretilmez.
REGIME_MAP = {"4h": "1d", "1d": "1w", "1w": "1M", "1M": None}

INTERVAL_SECONDS = {"4h": 14_400, "1d": 86_400, "1w": 604_800, "1M": 2_592_000}
INDICATOR_WARMUP_BARS = 220  # EMA200'un oturmasi icin aralik oncesi cekilen mum

# ── SINYAL AYARLARI (stratejinin karakterini belirler) ────────────────
# Uc katman: fiyat (trend/rsi/macd/volume) + turev piyasasi (funding/lsr/taker)
# + duygu (haber/makro/fng). Turev ve duygu bilesenleri "erken sinyal" tarafidir.
WEIGHTS = {
    # fiyat bilesenleri (grafik isaretleri ve backtest bunlari kullanir)
    "trend": 1.5,    # EMA20/50 trend yonu
    "rsi": 1.0,      # asiri alim/satimdan donus
    "macd": 1.0,     # momentum yon degisimi
    "volume": 0.5,   # hacim onayi
    # erken sinyal bilesenleri (sadece guncel oneriye eklenir)
    "news": 1.0,     # coin'e ozgu haber sentimenti (FinBERT)
    "macro": 0.75,   # genel ekonomi haber sentimenti (tum coinleri etkiler)
    "geo": 0.75,     # jeopolitik risk (savas/saldiri haberleri — ayri gorunur)
    "funding": 0.75, # funding rate — kalabaligin ters pozisyonu (kontrarian)
    "lsr": 0.5,      # buyuk oyuncu long/short orani (kontrarian)
    "taker": 0.5,    # taker al/sat hacim orani (momentum)
    "fng": 0.75,     # Korku & Hirs endeksi (kontrarian: asiri korku = firsat)
}
BUY_THRESHOLD = 3.0    # skor >= bu deger -> AL
SELL_THRESHOLD = -3.0  # skor <= bu deger -> SAT

RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65
VOLUME_SPIKE = 1.5     # hacim > 20-bar ortalamasi x bu katsayi

# Turev piyasasi esikleri
FUNDING_HOT = 0.0005     # 8 saatlik funding > %0.05 -> longlar asiri kalabalik
FUNDING_EXTREME = 0.001  # > %0.1 -> tehlike bolgesi
LSR_CROWDED_LONG = 2.5   # buyuk oyuncular asiri long
LSR_CROWDED_SHORT = 0.8  # asiri short (squeeze potansiyeli)

# Backtest'e dahil edilen duygu katmani: F&G endeksi (2018'den beri) ve
# funding rate (2019'dan beri) gecmisi ucretsiz mevcut. Kombine duygu skoru
# bu tabanin altina duserse (asiri hirs + kalabalik long) giris engellenir.
# Haber gecmisi ucretsiz kaynaklarda yok — haber bileseni canli oneriye ozel.
BACKTEST_SENTIMENT_FLOOR = -0.7

# Giris/cikis stratejisi (coklu varlik backtest taramalariyla secildi):
# giris = Donchian ust bant kirilimi + ust dilim rejimi pozitif,
# cikis = UYARLANABILIR trailing stop veya SAT skoru.
# Sabit hedef bilincli olarak YOK — boga trendinde kazananlar kosturulur.
# Trailing genisligi varligin oynakligina uyum saglar: S&P gibi sakin
# varliklarda dar iz her duzeltmede pozisyondan atiyordu (makas vergisi);
# kripto gibi oynak varliklarda genis iz kari geri veriyordu.
DONCHIAN_PERIOD = 20
TRAIL_ATR_MULT_VOLATILE = 3.0  # ATR > fiyatin %1.5'i (kripto, oynak hisse)
TRAIL_ATR_MULT_CALM = 5.0      # ATR < fiyatin %1.5'i (endeks, altin, doviz)
CALM_ATR_PCT = 0.015

# ── HABER AYARLARI ────────────────────────────────────────────────────
# NEWS_DECAY_HOURS: haber etkisinin azalma hizi (ussel). Kucuk = sadece taze
# haber sayilir; buyuk = gun boyu etki. Makro haberler daha yavas eskir.
NEWS_WINDOW_HOURS = 24
NEWS_DECAY_HOURS = 8
MACRO_WINDOW_HOURS = 48
MACRO_DECAY_HOURS = 16

# category: "crypto" -> coin bazinda eslestirilir, "macro" -> tum piyasayi etkiler
# lang: "tr" haberler GLOBAL makro skoruna katilmaz (BIST chatter'i BTC'yi
# etkilemesin) ama varlik eslestirmesiyle ilgili varligin haber skorunu besler.
RSS_FEEDS = {
    "Cointelegraph": {"url": "https://cointelegraph.com/rss", "category": "crypto", "lang": "en"},
    "Decrypt": {"url": "https://decrypt.co/feed", "category": "crypto", "lang": "en"},
    "Bitcoin Magazine": {"url": "https://bitcoinmagazine.com/feed", "category": "crypto", "lang": "en"},
    "CNBC Economy": {"url": "https://www.cnbc.com/id/20910258/device/rss/rss.html", "category": "macro", "lang": "en"},
    "MarketWatch": {"url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "category": "macro", "lang": "en"},
    "BBC World": {"url": "https://feeds.bbci.co.uk/news/world/rss.xml", "category": "macro", "lang": "en"},
    "Al Jazeera": {"url": "https://www.aljazeera.com/xml/rss/all.xml", "category": "macro", "lang": "en"},
    "BloombergHT": {"url": "https://www.bloomberght.com/rss", "category": "macro", "lang": "tr"},
    "Investing TR Borsa": {"url": "https://tr.investing.com/rss/news_25.rss", "category": "macro", "lang": "tr"},
}
TURKISH_SENTIMENT_MODEL = "savasy/bert-base-turkish-sentiment-cased"
FNG_URL = "https://api.alternative.me/fng/?limit=1"

# FinBERT finans haberlerinde iyidir ama savas/jeopolitik basliklari "notr"
# sayabiliyor (test edildi). Bu kelimeleri iceren makro haberler dogrudan
# guclu negatif kabul edilir ve panelde 🚨 ile one cikarilir.
GEOPOLITICAL_KEYWORDS = [
    "war", "strike", "strikes", "striking", "attack", "attacks", "missile",
    "invasion", "invades", "nuclear", "conflict", "retaliation", "airstrike",
    "bombing", "troops", "sanctions", "escalation", "ceasefire collapse",
    # Turkce kaynaklar icin
    "savas", "savaş", "saldiri", "saldırı", "füze", "fuze", "nükleer",
    "yaptırım", "yaptirim", "çatışma", "catisma",
]
GEOPOLITICAL_VALUE = -0.85  # bu haberlerin sentiment degeri (kuvvetli negatif)

# ── Servisler ─────────────────────────────────────────────────────────
BINANCE_BASE = "https://api.binance.com/api/v3"
BINANCE_FUTURES = "https://fapi.binance.com"
FINBERT_MODEL = "ProsusAI/finbert"
# Sirayla denenir; kurulu olan ilki kullanilir. 14b Turkce'de belirgin daha
# tutarli (7b mantik hatasi ve devrik cumle yapiyordu); 16GB M1 Pro'da ~9GB
# RAM kullanir, cevap suresi ~2x ama kalite farki buna deger.
OLLAMA_MODELS = ["qwen2.5:14b", "qwen2.5:7b", "llama3.2:3b"]
