from flask import Flask, request, jsonify
import requests
import os
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

scheduler = BackgroundScheduler()
scheduler.start()

def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def alarm_job(chat_id):
    send_message(chat_id, "⏰ ALARME ! Il est l'heure !")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')

        # النص المفترض أن يكون بصيغة HH:MM
        try:
            alarm_time = datetime.strptime(text, "%H:%M")
            now = datetime.now()
            run_time = now.replace(hour=alarm_time.hour, minute=alarm_time.minute, second=0, microsecond=0)
            
            # إذا الوقت مضى اليوم، نبرمجه ليوم غد
            if run_time < now:
                from datetime import timedelta
                run_time += timedelta(days=1)

            scheduler.add_job(alarm_job, 'date', run_date=run_time, args=[chat_id])
            send_message(chat_id, f"✅ Alarme programmée pour {run_time.strftime('%H:%M')} !")
        except ValueError:
            send_message(chat_id, "⚠️ Format invalide. Utilisez HH:MM")
            
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
