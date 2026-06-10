"""Telegram sinyal bildirici — dashboard kapaliyken sinyal kacirmamak icin.

Calisma mantigi: her 30 dakikada bir tum piyasalari gunluk dilimde tarar,
bir varligin sinyali degistiyse (orn. BEKLE -> AL) Telegram'a mesaj atar.
Onceki durum .notifier_state.json'da tutulur; ilk calistirmada mevcut durumu
kaydeder, mesaj atmaz (acilista spam olmasin).

Kurulum (bir kere):
1. Telegram'da @BotFather'a /newbot yaz, bot adini ver -> TOKEN verir.
2. Botunla bir mesajlasma baslat (herhangi bir sey yaz).
3. https://api.telegram.org/bot<TOKEN>/getUpdates adresine gir,
   "chat":{"id": ...} icindeki sayi CHAT_ID'dir.
4. Proje kokunde .secrets.json olustur:
   {"telegram_token": "123:ABC...", "chat_id": "123456789"}

Calistirma:  .venv/bin/python notifier.py
Arka planda: nohup .venv/bin/python notifier.py > notifier.log 2>&1 &
"""
import json
import time
from datetime import datetime
from pathlib import Path

import requests

from src.config import MARKETS
from src.data import binance, yahoo
from src.indicators.ta import add_indicators
from src.signals import engine

ROOT = Path(__file__).resolve().parent
SECRETS = ROOT / ".secrets.json"
STATE = ROOT / ".notifier_state.json"
CHECK_EVERY_SECONDS = 30 * 60
INTERVAL = "1d"


def load_secrets() -> dict | None:
    try:
        data = json.loads(SECRETS.read_text())
        if data.get("telegram_token") and data.get("chat_id"):
            return data
    except Exception:
        pass
    return None


def send_telegram(secrets: dict, text: str, chat_id: str | int | None = None) -> bool:
    """Mesaj yollar; chat_id verilmezse bot sahibine gider."""
    target = chat_id if chat_id is not None else secrets["chat_id"]
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{secrets['telegram_token']}/sendMessage",
            json={"chat_id": target, "text": text, "parse_mode": "Markdown"},
            timeout=15,
        )
        if not resp.ok:  # Markdown parse hatasi olabilir — duz metin dene
            resp = requests.post(
                f"https://api.telegram.org/bot{secrets['telegram_token']}/sendMessage",
                json={"chat_id": target, "text": text},
                timeout=15,
            )
        return resp.ok
    except Exception:
        return False


def get_updates(secrets: dict, offset: int | None) -> list[dict]:
    """Long-poll: yeni mesajlari bekler (20 sn) — ana dongunun bekleme noktasi."""
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{secrets['telegram_token']}/getUpdates",
            params={"offset": offset, "timeout": 20},
            timeout=30,
        )
        return resp.json().get("result", [])
    except Exception:
        time.sleep(5)  # ag hatasinda sikistirma
        return []


def fetch_price(symbol: str) -> float | None:
    """Alarm kontrolu icin tek varligin guncel fiyati (hafif istek)."""
    from src.config import MARKETS as _MK

    provider = next(
        (mk["provider"] for mk in _MK.values() if symbol in mk["assets"]), None
    )
    try:
        if provider == "binance":
            resp = requests.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": symbol}, timeout=10,
            )
            return float(resp.json()["price"])
        if provider == "yahoo":
            return yahoo.get_tickers([symbol]).get(symbol, {}).get("price")
    except Exception:
        pass
    return None


def current_action(provider: str, symbol: str) -> tuple[str, float] | None:
    """Fiyat + rejim bazli sade sinyal ve guncel fiyat.

    Bildirici hafif kalsin diye FinBERT/Ollama yuklenmez; kirilim + rejim
    zaten sinyalin belirleyicisidir.
    """
    try:
        source = yahoo if provider == "yahoo" else binance
        df = add_indicators(source.get_klines(symbol, INTERVAL))
        from src.config import REGIME_MAP

        higher = REGIME_MAP.get(INTERVAL)
        regime = None
        if higher:
            higher_df = source.get_klines(symbol, higher)
            if not higher_df.empty:
                regime = engine.regime_series(higher_df)
        scored = engine.compute_scores(df, regime)
        rec = engine.current_recommendation(scored)
        return rec["action"], rec["price"]
    except Exception:
        return None


def scan() -> dict[str, tuple[str, float]]:
    results = {}
    for market in MARKETS.values():
        for symbol in market["assets"]:
            res = current_action(market["provider"], symbol)
            if res:
                results[symbol] = res
    return results


def main() -> None:
    secrets = load_secrets()
    if secrets is None:
        print("HATA: .secrets.json bulunamadi veya eksik — dosya basindaki kurulum adimlarina bak.")
        return
    print(f"[{datetime.now():%H:%M}] Bildirici basladi — {CHECK_EVERY_SECONDS // 60} dk'da bir tarama.")

    previous = {}
    if STATE.exists():
        try:
            previous = json.loads(STATE.read_text())
        except Exception:
            previous = {}

    last_report_day = None
    if STATE.exists():
        try:
            last_report_day = json.loads(STATE.read_text()).get("_report_day")
        except Exception:
            pass

    from src import assistant
    from src.portfolio import alarms

    offset = None
    last_scan = 0.0
    last_alarm_check = 0.0

    while True:
        # 1) Telegram mesajlari (long-poll 20 sn — dongunun bekleme noktasi)
        # Herkes soru sorabilir; alarm gibi durum degistiren komutlar ve
        # sinyal bildirimleri/sabah raporu yalnizca bot sahibine ozeldir.
        for update in get_updates(secrets, offset):
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "")
            if chat_id is None or not text:
                continue
            is_owner = str(chat_id) == str(secrets["chat_id"])
            who = "sahip" if is_owner else f"misafir:{chat_id}"
            print(f"[{datetime.now():%H:%M}] mesaj ({who}): {text[:60]}")
            if not text.startswith("/"):
                send_telegram(secrets, "🤔 Bakiyorum, birkac saniye...", chat_id)
            try:
                reply = assistant.handle_text(
                    text,
                    {s: a for s, a in previous.items() if not s.startswith("_")},
                    chat_id=str(chat_id), is_owner=is_owner,
                )
            except Exception as exc:
                reply = f"Hata olustu: {exc}"
            send_telegram(secrets, reply, chat_id)
            # Sohbet hafizasi: kullanici basina — takip sorulari baglam bulsun
            assistant.remember(str(chat_id), "user", text)
            assistant.remember(str(chat_id), "assistant", reply)

        # 2) Fiyat alarmlari (~60 sn'de bir, yalniz alarmli varliklar)
        now_ts = time.time()
        if now_ts - last_alarm_check >= 60 and alarms.list_alarms():
            prices = {}
            for a in alarms.list_alarms():
                p = fetch_price(a["symbol"])
                if p is not None:
                    prices[a["symbol"]] = p
            for hit in alarms.check(prices):
                from src.config import ALL_ASSETS

                arrow = "⬆️ ustune cikti" if hit["direction"] == "above" else "⬇️ altina dustu"
                send_telegram(
                    secrets,
                    f"🔔 *ALARM*: {ALL_ASSETS.get(hit['symbol'], {}).get('name', hit['symbol'])} "
                    f"{hit['level']:,.4g} seviyesinin {arrow} (su an {hit['price']:,.4g})",
                )
                print(f"[{datetime.now():%H:%M}] alarm tetiklendi: {hit['symbol']}")
            last_alarm_check = now_ts

        # 3) Tam sinyal taramasi (30 dk'da bir)
        if now_ts - last_scan < CHECK_EVERY_SECONDS:
            continue
        last_scan = now_ts
        results = scan()
        actions = {s: a for s, (a, _) in results.items()}

        # Sinyal karnesi: sanal pozisyonlari guncelle
        from src.portfolio import scorecard

        for note in scorecard.record_scan(results):
            print(f"[{datetime.now():%H:%M}] karne — {note}")

        # Sinyal degisim bildirimleri
        changes = []
        for symbol, action in actions.items():
            old = previous.get(symbol)
            if old is not None and old != action and action in ("AL", "SAT"):
                from src.config import ALL_ASSETS

                emoji = "🟢" if action == "AL" else "🔴"
                price = results[symbol][1]
                changes.append(
                    f"{emoji} *{ALL_ASSETS[symbol]['name']}*: {old} → *{action}* @ {price:,.4g}"
                )
        if changes and previous:
            sent = send_telegram(secrets, "📈 AL-SAT sinyal degisimi\n" + "\n".join(changes))
            print(f"[{datetime.now():%H:%M}] {len(changes)} degisim, telegram: {'ok' if sent else 'HATA'}")
        else:
            print(f"[{datetime.now():%H:%M}] degisim yok ({len(actions)} varlik tarandi)")

        # Sabah raporu: 09:00'dan sonraki ilk taramada, gunde bir kez
        today = datetime.now().strftime("%Y-%m-%d")
        if datetime.now().hour >= 9 and last_report_day != today:
            from src.reporting import build_morning_report

            try:
                report = build_morning_report(actions)
                sent = send_telegram(secrets, report)
                print(f"[{datetime.now():%H:%M}] sabah raporu telegram: {'ok' if sent else 'HATA'}")
                last_report_day = today
            except Exception as exc:
                print(f"[{datetime.now():%H:%M}] sabah raporu HATA: {exc}")

        previous = actions
        STATE.write_text(json.dumps({**actions, "_report_day": last_report_day}))


if __name__ == "__main__":
    main()
