from flask import Flask, request, jsonify
import requests
import os
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

scheduler = BackgroundScheduler()
scheduler.start()

def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def alarm_job(chat_id):
    for _ in range(6):  # 6 مرات كل 5 ثواني => 30 ثانية
        send_message(chat_id, "⏰ ALARME ! Le temps est écoulé.")
        import time; time.sleep(5)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        if text.isdigit():
            delay = int(text)
            run_time = datetime.now() + timedelta(seconds=delay)
            scheduler.add_job(alarm_job, 'date', run_date=run_time, args=[chat_id])
            send_message(chat_id, f"✅ Minuteur réglé pour {delay} secondes !")
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
