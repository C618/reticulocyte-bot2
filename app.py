from flask import Flask, request
import requests
import os

app = Flask(__name__)

# 🔑 ضع التوكن الخاص بك هنا
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# 📌 لوحة الأزرار العامة
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "/calc"}, {"text": "/plaquettes"}],
            [{"text": "/dilution"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# 📌 رسالة الترحيب عند البداية
def send_welcome_start(chat_id):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": (
            "👋 Bonjour ! Je suis votre bot médical.\n\n"
            "🔹 /calc → Calcul du taux de réticulocytes\n"
            "🔹 /plaquettes → Calcul des plaquettes\n"
            "🔹 /dilution → Préparer une dilution"
        ),
        "reply_markup": get_main_keyboard()
    }
    requests.post(url, json=data)

# 📌 رسالة بعد نهاية أي حساب
def send_welcome_end(chat_id):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": (
            "✅ Calcul terminé !\n\n"
            "👋 Vous voulez essayer un autre calcul ?"
        ),
        "reply_markup": get_main_keyboard()
    }
    requests.post(url, json=data)


# ✅ حساب réticulocytes
def calc_reticulocytes(chat_id, num, total):
    try:
        taux = (num / total) * 100
        message = f"📊 Taux de réticulocytes : {taux:.2f} %"
    except Exception as e:
        message = f"⚠️ Erreur: {e}"
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": message})
    send_welcome_end(chat_id)


# ✅ حساب plaquettes
def calc_plaquettes(chat_id, num, dilution, volume):
    try:
        result = (num * dilution * 20) / volume
        message = f"🧪 Numération plaquettaire : {result:.0f} /mm³"
    except Exception as e:
        message = f"⚠️ Erreur: {e}"
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": message})
    send_welcome_end(chat_id)


# ✅ dilution
def calc_dilution(chat_id, ratio, volume_total=None):
    try:
        num, den = map(int, ratio.split('/'))
        if volume_total:
            volume_substance = volume_total / den
            volume_diluent = volume_total - volume_substance
            message = (
                f"⚗️ Dilution {ratio} pour un volume total de {volume_total} ml :\n"
                f"👉 {volume_substance:.2f} ml de substance\n"
                f"👉 {volume_diluent:.2f} ml de diluant"
            )
        else:
            message = (
                f"⚗️ Dilution {ratio} :\n"
                f"👉 Prendre {num} part(s) de substance\n"
                f"👉 Ajouter {den - num} part(s) de diluant"
            )
    except Exception as e:
        message = f"⚠️ Erreur: {e}"

    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": message})
    send_welcome_end(chat_id)


# 📌 التعامل مع الرسائل
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            send_welcome_start(chat_id)

        elif text.startswith("/calc"):
            # مثال بسيط: /calc 25 100
            parts = text.split()
            if len(parts) == 3:
                calc_reticulocytes(chat_id, int(parts[1]), int(parts[2]))
            else:
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "📝 Utilisation: /calc [num] [total]"
                })

        elif text.startswith("/plaquettes"):
            # مثال: /plaquettes 200 20 1
            parts = text.split()
            if len(parts) == 4:
                calc_plaquettes(chat_id, int(parts[1]), int(parts[2]), int(parts[3]))
            else:
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "📝 Utilisation: /plaquettes [num] [dilution] [volume]"
                })

        elif text.startswith("/dilution"):
            # مثال: /dilution 1/2 10
            parts = text.split()
            if len(parts) == 2:
                calc_dilution(chat_id, parts[1])
            elif len(parts) == 3:
                calc_dilution(chat_id, parts[1], float(parts[2]))
            else:
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "📝 Utilisation: /dilution [ratio] [volume_total?]"
                })

    return {"ok": True}
