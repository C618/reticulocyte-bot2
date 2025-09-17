from flask import Flask, request, jsonify
import requests, os, json, re
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

user_states = {}
user_languages = {}
user_alarms = {}  # {chat_id: [{'name':..., 'time':..., 'job_id':...}]}
calculations_history = []

scheduler = BackgroundScheduler()
scheduler.start()

# ------------------- Claviers -------------------
def get_main_keyboard(lang='fr'):
    keyboards = {
        'fr': [
            ['🔢 Réticulocytes', '🩸 Plaquettes'],
            ['🧪 Dilution', '⚙️ Paramètres'],
            ['⏰ Rappels', 'ℹ️ Aide', '🔄 Langue']
        ],
        'en': [
            ['🔢 Reticulocytes', '🩸 Platelets'],
            ['🧪 Dilution', '⚙️ Settings'],
            ['⏰ Alarms', 'ℹ️ Help', '🔄 Language']
        ],
        'ar': [
            ['🔢 الخلايا الشبكية', '🩸 الصفائح الدموية'],
            ['🧪 التخفيف', '⚙️ الإعدادات'],
            ['⏰ المنبهات', 'ℹ️ المساعدة', '🔄 اللغة']
        ]
    }
    return {'keyboard': keyboards.get(lang, keyboards['fr']), 'resize_keyboard': True}

def get_alarm_keyboard(lang='fr'):
    texts = {'fr': ['📝 Ajouter un rappel','📋 Mes rappels','❌ Annuler'],
             'en': ['📝 Add alarm','📋 My alarms','❌ Cancel'],
             'ar': ['📝 إضافة منبه','📋 منبهاتي','❌ إلغاء']}
    return {'keyboard': [[texts[lang][0]], [texts[lang][1]], [texts[lang][2]]], 'resize_keyboard': True}

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode: data["parse_mode"] = parse_mode
    try: requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=data, timeout=10)
    except: pass

# ------------------- Webhook -------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text','')
        lang = user_languages.get(chat_id,'fr')

        # ---------- Commandes de base ----------
        if text in ['/start','🔙 Retour','🔙 Back','🔙 رجوع']:
            send_welcome(chat_id, lang)
            user_states[chat_id] = {'step':0}

        elif text in ['ℹ️ Aide','ℹ️ Help','ℹ️ المساعدة','/help']:
            send_message(chat_id, "ℹ️ Texte d'aide...", get_main_keyboard(lang))

        elif text in ['🔢 Réticulocytes','🔢 Reticulocytes','🔢 الخلايا الشبكية','/calc']:
            send_message(chat_id,"🔢 Combien de champs...",{'keyboard':[["1","2","3","4","5"]],'resize_keyboard':True})
            user_states[chat_id] = {'step':50,'type':'reti','reti_counts':[],'rbc_counts':[],'nb_champs':None}

        elif text in ['🩸 Plaquettes','🩸 Platelets','🩸 الصفائح الدموية','/plaquettes']:
            send_message(chat_id,"🩸 Combien de champs...",{'keyboard':[["1","2","3","4","5"]],'resize_keyboard':True})
            user_states[chat_id] = {'step':100,'type':'plaq','plaq_counts':[],'rbc_counts':[],'gr_auto':None,'nb_champs':None}

        elif text in ['🧪 Dilution','🧪 التخفيف','/dilution']:
            send_message(chat_id,"🧪 Entrez la dilution souhaitée...",{'keyboard':[["1/2","1/5","1/10"]],'resize_keyboard':True})
            user_states[chat_id] = {'step':400,'type':'dilution'}

        elif text in ['⚙️ Paramètres','⚙️ Settings','⚙️ الإعدادات']:
            send_message(chat_id,"⚙️ Paramètres...",{'keyboard':[['🔙 Retour'],['🗑️ Effacer historique'],['📊 Statistiques']],'resize_keyboard':True})

        elif text in ['🔄 Langue','🔄 Language','🔄 اللغة']:
            send_message(chat_id,"🌍 Choisissez votre langue:",{'keyboard':[["🇫🇷 Français","🇬🇧 English"],["🇸🇦 العربية","🔙 Retour"]],'resize_keyboard':True})

        elif text in ['🇫🇷 Français']:
            user_languages[chat_id] = 'fr'
            send_welcome(chat_id,'fr')

        elif text in ['🇬🇧 English']:
            user_languages[chat_id] = 'en'
            send_welcome(chat_id,'en')

        elif text in ['🇸🇦 العربية']:
            user_languages[chat_id] = 'ar'
            send_welcome(chat_id,'ar')

        # ---------- Section Rappels ----------
        elif text in ['⏰ Rappels','⏰ Alarms','⏰ المنبهات']:
            send_message(chat_id,"📌 Choisissez une option:", get_alarm_keyboard(lang))

        elif text in ['📝 Ajouter un rappel','📝 Add alarm','📝 إضافة منبه']:
            send_message(chat_id,"✍️ Envoyez votre rappel:\n- in 60 nom_du_rappel\n- YYYY-MM-DD HH:MM nom_du_rappel")
            user_states[chat_id] = {'awaiting_alarm':True,'lang':lang}

        elif chat_id in user_states and user_states[chat_id].get('awaiting_alarm'):
            handle_alarm_input(chat_id, text)

    elif 'callback_query' in data:
        handle_callback(data['callback_query'])

    return jsonify({'status':'ok'})

# ------------------- Fonctions Rappels -------------------
def handle_alarm_input(chat_id, text):
    try:
        if text.startswith("in "):
            parts = text.split(" ",2)
            minutes = int(parts[1])
            name = parts[2]
            alarm_time = datetime.now() + timedelta(minutes=minutes)
        else:
            date_str, time_str, name = text.split(" ",2)
            alarm_time = datetime.strptime(date_str+" "+time_str, "%Y-%m-%d %H:%M")
        job = scheduler.add_job(send_alarm,'date',run_date=alarm_time,args=[chat_id,name])
        user_alarms.setdefault(chat_id,[]).append({'name':name,'time':str(alarm_time),'job_id':job.id})
        send_message(chat_id,f"⏰ Rappel '{name}' programmé à {alarm_time}")
        user_states[chat_id]['awaiting_alarm'] = False
    except:
        send_message(chat_id,"❌ Format incorrect! Essayez de nouveau.")

def send_alarm(chat_id,name):
    keyboard = {'inline_keyboard':[
        [{'text':'⏱️ Reporter 5 min','callback_data':f'postpone|{name}|5'}],
        [{'text':'✅ Terminer','callback_data':f'done|{name}'}]
    ]}
    send_message(chat_id,f"🚨 Rappel: {name}",reply_markup=keyboard)

def handle_callback(callback):
    chat_id = callback['message']['chat']['id']
    data = callback['data']
    if data.startswith('postpone'):
        _, name, mins = data.split('|')
        mins = int(mins)
        alarms = user_alarms.get(chat_id,[])
        for alarm in alarms:
            if alarm['name']==name:
                scheduler.remove_job(alarm['job_id'])
                new_time = datetime.now() + timedelta(minutes=mins)
                job = scheduler.add_job(send_alarm,'date',run_date=new_time,args=[chat_id,name])
                alarm['time'] = str(new_time)
                alarm['job_id'] = job.id
                send_message(chat_id,f"⏱️ Rappel '{name}' reporté à {new_time}")
                break
    elif data.startswith('done'):
        _, name = data.split('|')
        alarms = user_alarms.get(chat_id,[])
        for alarm in alarms:
            if alarm['name']==name:
                scheduler.remove_job(alarm['job_id'])
                alarms.remove(alarm)
                send_message(chat_id,f"✅ Rappel '{name}' terminé!")
                break

# ------------------- Welcome -------------------
def send_welcome(chat_id,lang='fr'):
    messages = {'fr':"👋 Bonjour! Choisissez une option:",'en':"👋 Hello! Choose an option:",'ar':"👋 مرحبًا! اختر خيارًا:"}
    send_message(chat_id,messages.get(lang,'Hello'),get_main_keyboard(lang))

# ------------------- Webhook -------------------
def set_webhook():
    try:
        url = f"{TELEGRAM_API_URL}/setWebhook?url={WEBHOOK_URL}/webhook"
        r = requests.get(url)
        print("Webhook set:", r.json())
    except Exception as e: print("Error:", e)

if __name__=='__main__':
    set_webhook()
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port, debug=False)
