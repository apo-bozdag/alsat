#!/bin/bash
# AL-SAT baslatici — dashboard + telegram bildirici + ollama
# Kullanim:  ./calistir.sh           (baslat / zaten calisanlari atla)
#            ./calistir.sh durdur    (hepsini durdur)
#            ./calistir.sh durum     (ne calisiyor goster)
cd "$(dirname "$0")"

durum() {
    pgrep -f "streamlit run app.py" >/dev/null && echo "✅ Dashboard calisiyor → http://localhost:8501" || echo "❌ Dashboard kapali"
    pgrep -f "python -u notifier.py" >/dev/null && echo "✅ Telegram bildirici calisiyor" || echo "❌ Bildirici kapali"
    pgrep -x ollama >/dev/null && echo "✅ Ollama calisiyor" || echo "❌ Ollama kapali (AI yorum/bot cevaplari calismaz)"
}

if [ "$1" = "durdur" ]; then
    pkill -f "streamlit run app.py" && echo "Dashboard durduruldu"
    pkill -f "python -u notifier.py" && echo "Bildirici durduruldu"
    exit 0
fi

if [ "$1" = "durum" ]; then
    durum
    exit 0
fi

# Ollama (AI icin — kuruluysa)
if command -v ollama >/dev/null && ! pgrep -x ollama >/dev/null; then
    nohup ollama serve > /dev/null 2>&1 &
    echo "Ollama baslatildi"
fi

# Dashboard
if ! pgrep -f "streamlit run app.py" >/dev/null; then
    nohup .venv/bin/streamlit run app.py --server.headless true > /dev/null 2>&1 &
    echo "Dashboard baslatildi"
fi

# Telegram bildirici (.secrets.json varsa)
if [ -f .secrets.json ] && ! pgrep -f "python -u notifier.py" >/dev/null; then
    nohup .venv/bin/python -u notifier.py > notifier.log 2>&1 &
    echo "Bildirici baslatildi (log: notifier.log)"
fi

sleep 3
echo "---"
durum
