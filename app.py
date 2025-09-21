from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Token du bot Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_message(chat_id, text):
    """إرسال رسالة عبر بوت تلغرام"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)


def calculate_remainder(a, b):
    """حساب باقي القسمة"""
    try:
        a = float(a)
        b = float(b)
        q = a // b
        r = a - q * b
        return r
    except Exception as e:
        return f"خطأ: {e}"


@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال رسائل من تلغرام"""
    data = request.get_json()
    
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        # نفترض أن المستخدم يرسل الأرقام بهذا الشكل: "10 3"
        parts = text.split()
        if len(parts) == 2:
            result = calculate_remainder(parts[0], parts[1])
            send_message(chat_id, f"باقي القسمة: {result}")
        else:
            send_message(chat_id, "الرجاء إرسال رقمين مفصولين بمسافة مثل: 10 3")
    
    return jsonify({"status": "ok"})


def set_webhook():
    """تعيين webhook للبوت"""
    webhook_url = os.environ.get('WEBHOOK_URL') + '/webhook'
    url = f"{TELEGRAM_API_URL}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(url)
        print(f"Webhook set: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error setting webhook: {e}")


if __name__ == '__main__':
    set_webhook()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
