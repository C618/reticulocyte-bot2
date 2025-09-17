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

def get_numeric_keyboard(lang='fr'):
    cancel_text = {'fr': '❌ Annuler', 'en': '❌ Cancel', 'ar': '❌ إلغاء'}
    return {
        'keyboard': [
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '10'],
            [cancel_text[lang]]
        ],
        'resize_keyboard': True
    }

def get_dilution_keyboard(lang='fr'):
    cancel_text = {'fr': '❌ Annuler', 'en': '❌ Cancel', 'ar': '❌ إلغاء'}
    return {
        'keyboard': [
            ['1/2', '1/5', '1/10'],
            ['1/20', '1/50', '1/100'],
            [cancel_text[lang]]
        ],
        'resize_keyboard': True
    }

def get_alarm_keyboard(lang='fr'):
    texts = {'fr': ['📝 Ajouter un rappel','📋 Mes rappels','🔙 Retour'],
             'en': ['📝 Add alarm','📋 My alarms','🔙 Back'],
             'ar': ['📝 إضافة منبه','📋 منبهاتي','🔙 رجوع']}
    return {'keyboard': [[texts[lang][0]], [texts[lang][1]], [texts[lang][2]]], 'resize_keyboard': True}

def get_cancel_keyboard(lang='fr'):
    cancel_text = {'fr': '❌ Annuler', 'en': '❌ Cancel', 'ar': '❌ إلغاء'}
    return {'keyboard': [[cancel_text[lang]]], 'resize_keyboard': True}

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_markup: 
        data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode: 
        data["parse_mode"] = parse_mode
    try: 
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=data, timeout=10)
    except: 
        pass

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
            help_text = {
                'fr': "ℹ️ *AIDE*\n\n🔢 Réticulocytes - Calcul des réticulocytes\n🩸 Plaquettes - Calcul des plaquettes\n🧪 Dilution - Préparer des dilutions\n⏰ Rappels - Gérer les rappels\n⚙️ Paramètres - Options du bot",
                'en': "ℹ️ *HELP*\n\n🔢 Reticulocytes - Reticulocyte count\n🩸 Platelets - Platelet count\n🧪 Dilution - Prepare dilutions\n⏰ Alarms - Manage alarms\n⚙️ Settings - Bot options",
                'ar': "ℹ️ *المساعدة*\n\n🔢 الخلايا الشبكية - حساب الخلايا الشبكية\n🩸 الصفائح الدموية - حساب الصفائح الدموية\n🧪 التخفيف - تحضير المحاليل المخففة\n⏰ المنبهات - إدارة المنبهات\n⚙️ الإعدادات - خيارات البوت"
            }
            send_message(chat_id, help_text.get(lang, help_text['fr']), get_main_keyboard(lang), parse_mode='Markdown')

        elif text in ['🔢 Réticulocytes','🔢 Reticulocytes','🔢 الخلايا الشبكية','/calc']:
            field_text = {
                'fr': "🔢 Combien de champs voulez-vous analyser pour les réticulocytes ?",
                'en': "🔢 How many fields do you want to analyze for reticulocytes?",
                'ar': "🔢 كم حقلًا تريد تحليله للخلايا الشبكية؟"
            }
            send_message(chat_id, field_text.get(lang, field_text['fr']), get_numeric_keyboard(lang))
            user_states[chat_id] = {'step':50,'type':'reti','reti_counts':[],'rbc_counts':[],'nb_champs':None}

        elif text in ['🩸 Plaquettes','🩸 Platelets','🩸 الصفائح الدموية','/plaquettes']:
            field_text = {
                'fr': "🩸 Combien de champs voulez-vous analyser pour les plaquettes ?",
                'en': "🩸 How many fields do you want to analyze for platelets?",
                'ar': "🩸 كم حقلًا تريد تحليله للصفائح الدموية؟"
            }
            send_message(chat_id, field_text.get(lang, field_text['fr']), get_numeric_keyboard(lang))
            user_states[chat_id] = {'step':100,'type':'plaq','plaq_counts':[],'rbc_counts':[],'gr_auto':None,'nb_champs':None}

        elif text in ['🧪 Dilution','🧪 التخفيف','/dilution']:
            dilution_text = {
                'fr': "🧪 Entrez la dilution souhaitée (ex: 1/2, 1/10) :",
                'en': "🧪 Enter the desired dilution (ex: 1/2, 1/10):",
                'ar': "🧪 أدخل التخفيف المطلوب (مثال: 1/2, 1/10):"
            }
            send_message(chat_id, dilution_text.get(lang, dilution_text['fr']), get_dilution_keyboard(lang))
            user_states[chat_id] = {'step':400,'type':'dilution'}

        elif text in ['⚙️ Paramètres','⚙️ Settings','⚙️ الإعدادات']:
            settings_text = {
                'fr': "⚙️ Paramètres:\n- Langue: {}\n- Historique: Activé".format('Français' if lang=='fr' else 'English' if lang=='en' else 'العربية'),
                'en': "⚙️ Settings:\n- Language: {}\n- History: Enabled".format('French' if lang=='fr' else 'English' if lang=='en' else 'Arabic'),
                'ar': "⚙️ الإعدادات:\n- اللغة: {}\n- السجل: مفعل".format('الفرنسية' if lang=='fr' else 'الإنجليزية' if lang=='en' else 'العربية')
            }
            send_message(chat_id, settings_text.get(lang, settings_text['fr']), get_main_keyboard(lang))

        elif text in ['🔄 Langue','🔄 Language','🔄 اللغة']:
            lang_text = {
                'fr': "🌍 Choisissez votre langue:",
                'en': "🌍 Choose your language:",
                'ar': "🌍 اختر لغتك:"
            }
            send_message(chat_id, lang_text.get(lang, lang_text['fr']), 
                        {'keyboard':[["🇫🇷 Français","🇬🇧 English"],["🇸🇦 العربية","🔙 Retour"]],'resize_keyboard':True})

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
            alarm_text = {
                'fr': "⏰ Gestion des rappels:",
                'en': "⏰ Alarm management:",
                'ar': "⏰ إدارة المنبهات:"
            }
            send_message(chat_id, alarm_text.get(lang, alarm_text['fr']), get_alarm_keyboard(lang))

        elif text in ['📝 Ajouter un rappel','📝 Add alarm','📝 إضافة منبه']:
            alarm_help = {
                'fr': "✍️ Envoyez votre rappel:\n- in 60 nom_du_rappel\n- YYYY-MM-DD HH:MM nom_du_rappel",
                'en': "✍️ Send your alarm:\n- in 60 alarm_name\n- YYYY-MM-DD HH:MM alarm_name",
                'ar': "✍️ أرسل منبهك:\n- in 60 اسم_المنبه\n- YYYY-MM-DD HH:MM اسم_المنبه"
            }
            send_message(chat_id, alarm_help.get(lang, alarm_help['fr']), get_cancel_keyboard(lang))
            user_states[chat_id] = {'awaiting_alarm':True,'lang':lang}

        elif text in ['📋 Mes rappels','📋 My alarms','📋 منبهاتي']:
            alarms = user_alarms.get(chat_id, [])
            if alarms:
                alarm_list = "\n".join([f"⏰ {alarm['name']} - {alarm['time']}" for alarm in alarms])
                alarm_text = {
                    'fr': f"📋 Vos rappels:\n{alarm_list}",
                    'en': f"📋 Your alarms:\n{alarm_list}",
                    'ar': f"📋 منبهاتك:\n{alarm_list}"
                }
            else:
                alarm_text = {
                    'fr': "📋 Aucun rappel programmé",
                    'en': "📋 No alarms scheduled",
                    'ar': "📋 لا توجد منبهات مجدولة"
                }
            send_message(chat_id, alarm_text.get(lang, alarm_text['fr']), get_alarm_keyboard(lang))

        elif text in ['❌ Annuler','❌ Cancel','❌ إلغاء']:
            cancel_text = {
                'fr': "❌ Opération annulée",
                'en': "❌ Operation cancelled",
                'ar': "❌ تم إلغاء العملية"
            }
            send_message(chat_id, cancel_text.get(lang, cancel_text['fr']), get_main_keyboard(lang))
            user_states[chat_id] = {'step':0}

        # ---------- Gestion des inputs ----------
        elif chat_id in user_states:
            if user_states[chat_id].get('awaiting_alarm'):
                handle_alarm_input(chat_id, text)
            else:
                handle_calcul_input(chat_id, text, lang)

    elif 'callback_query' in data:
        handle_callback(data['callback_query'])

    return jsonify({'status':'ok'})

# ------------------- Gestion des inputs de calcul -------------------
def handle_calcul_input(chat_id, text, lang):
    state = user_states[chat_id]
    
    # Vérifier si c'est une commande d'annulation
    if text in ['❌ Annuler','❌ Cancel','❌ إلغاء']:
        cancel_text = {
            'fr': "❌ Opération annulée",
            'en': "❌ Operation cancelled",
            'ar': "❌ تم إلغاء العملية"
        }
        send_message(chat_id, cancel_text.get(lang, cancel_text['fr']), get_main_keyboard(lang))
        user_states[chat_id] = {'step':0}
        return
    
    try:
        if state.get('type') != 'dilution':
            value = int(text)
            if value < 0:
                raise ValueError
        else:
            value = text

        if state.get('type') == 'reti':
            handle_reti(chat_id, value, lang)
        elif state.get('type') == 'plaq':
            handle_plaquettes(chat_id, value, lang)
        elif state.get('type') == 'dilution':
            handle_dilution(chat_id, value, lang)
    
    except ValueError:
        error_text = {
            'fr': "⚠️ Veuillez entrer un nombre valide",
            'en': "⚠️ Please enter a valid number",
            'ar': "⚠️ الرجاء إدخال رقم صحيح"
        }
        send_message(chat_id, error_text.get(lang, error_text['fr']), get_numeric_keyboard(lang))

# ------------------- Fonctions de calcul -------------------
def handle_reti(chat_id, value, lang):
    state = user_states[chat_id]

    if state['step'] == 50:
        state['nb_champs'] = value
        reti_text = {
            'fr': f"🔢 Entrez le nombre de réticulocytes dans le Champ 1 :",
            'en': f"🔢 Enter the number of reticulocytes in Field 1:",
            'ar': f"🔢 أدخل عدد الخلايا الشبكية في الحقل 1:"
        }
        send_message(chat_id, reti_text.get(lang, reti_text['fr']), get_numeric_keyboard(lang))
        state['step'] = 51
        return

    # ... (le reste du code pour handle_reti, handle_plaquettes, handle_dilution)

# ------------------- Fonctions Rappels -------------------
def handle_alarm_input(chat_id, text):
    lang = user_states[chat_id].get('lang', 'fr')
    
    if text in ['❌ Annuler','❌ Cancel','❌ إلغاء']:
        cancel_text = {
            'fr': "❌ Création de rappel annulée",
            'en': "❌ Alarm creation cancelled",
            'ar': "❌ تم إلغاء إنشاء المنبه"
        }
        send_message(chat_id, cancel_text.get(lang, cancel_text['fr']), get_alarm_keyboard(lang))
        user_states[chat_id] = {'step':0}
        return
    
    try:
        if text.startswith("in "):
            parts = text.split(" ", 2)
            minutes = int(parts[1])
            name = parts[2] if len(parts) > 2 else "Rappel"
            alarm_time = datetime.now() + timedelta(minutes=minutes)
        else:
            # Essayer de parser la date et l'heure
            parts = text.split(" ", 2)
            if len(parts) >= 3:
                date_str, time_str, name = parts[0], parts[1], parts[2]
                alarm_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            else:
                raise ValueError("Format incorrect")
        
        job = scheduler.add_job(send_alarm, 'date', run_date=alarm_time, args=[chat_id, name])
        user_alarms.setdefault(chat_id, []).append({'name': name, 'time': str(alarm_time), 'job_id': job.id})
        
        success_text = {
            'fr': f"⏰ Rappel '{name}' programmé à {alarm_time.strftime('%Y-%m-%d %H:%M')}",
            'en': f"⏰ Alarm '{name}' scheduled for {alarm_time.strftime('%Y-%m-%d %H:%M')}",
            'ar': f"⏰ تم جدولة المنبه '{name}' في {alarm_time.strftime('%Y-%m-%d %H:%M')}"
        }
        send_message(chat_id, success_text.get(lang, success_text['fr']), get_alarm_keyboard(lang))
        user_states[chat_id] = {'step':0}
        
    except Exception as e:
        error_text = {
            'fr': "❌ Format incorrect! Utilisez:\n- in 60 nom_du_rappel\n- YYYY-MM-DD HH:MM nom_du_rappel",
            'en': "❌ Incorrect format! Use:\n- in 60 alarm_name\n- YYYY-MM-DD HH:MM alarm_name",
            'ar': "❌ تنسيق غير صحيح! استخدم:\n- in 60 اسم_المنبه\n- YYYY-MM-DD HH:MM اسم_المنبه"
        }
        send_message(chat_id, error_text.get(lang, error_text['fr']), get_alarm_keyboard(lang))

def send_alarm(chat_id, name):
    keyboard = {'inline_keyboard':[
        [{'text':'⏱️ Reporter 5 min','callback_data':f'postpone|{name}|5'}],
        [{'text':'✅ Terminer','callback_data':f'done|{name}'}]
    ]}
    alarm_text = {
        'fr': f"🚨 Rappel: {name}",
        'en': f"🚨 Alarm: {name}",
        'ar': f"🚨 منبه: {name}"
    }
    lang = user_languages.get(chat_id, 'fr')
    send_message(chat_id, alarm_text.get(lang, alarm_text['fr']), reply_markup=keyboard)

def handle_callback(callback):
    chat_id = callback['message']['chat']['id']
    data = callback['data']
    lang = user_languages.get(chat_id, 'fr')
    
    if data.startswith('postpone'):
        _, name, mins = data.split('|')
        mins = int(mins)
        alarms = user_alarms.get(chat_id, [])
        for alarm in alarms:
            if alarm['name'] == name:
                try:
                    scheduler.remove_job(alarm['job_id'])
                    new_time = datetime.now() + timedelta(minutes=mins)
                    job = scheduler.add_job(send_alarm, 'date', run_date=new_time, args=[chat_id, name])
                    alarm['time'] = str(new_time)
                    alarm['job_id'] = job.id
                    postpone_text = {
                        'fr': f"⏱️ Rappel '{name}' reporté à {new_time.strftime('%H:%M')}",
                        'en': f"⏱️ Alarm '{name}' postponed to {new_time.strftime('%H:%M')}",
                        'ar': f"⏱️ تم تأجيل المنبه '{name}' إلى {new_time.strftime('%H:%M')}"
                    }
                    send_message(chat_id, postpone_text.get(lang, postpone_text['fr']))
                except:
                    pass
                break
                
    elif data.startswith('done'):
        _, name = data.split('|')
        alarms = user_alarms.get(chat_id, [])
        for alarm in alarms:
            if alarm['name'] == name:
                try:
                    scheduler.remove_job(alarm['job_id'])
                    alarms.remove(alarm)
                    done_text = {
                        'fr': f"✅ Rappel '{name}' terminé!",
                        'en': f"✅ Alarm '{name}' completed!",
                        'ar': f"✅ تم إنهاء المنبه '{name}'!"
                    }
                    send_message(chat_id, done_text.get(lang, done_text['fr']))
                except:
                    pass
                break

# ------------------- Welcome -------------------
def send_welcome(chat_id, lang='fr'):
    messages = {
        'fr': "👋 Bonjour! Choisissez une option:",
        'en': "👋 Hello! Choose an option:",
        'ar': "👋 مرحبًا! اختر خيارًا:"
    }
    send_message(chat_id, messages.get(lang, 'Hello'), get_main_keyboard(lang))

# ------------------- Webhook Setup -------------------
def set_webhook():
    try:
        url = f"{TELEGRAM_API_URL}/setWebhook?url={WEBHOOK_URL}/webhook"
        r = requests.get(url)
        print("Webhook set:", r.json())
    except Exception as e:
        print("Error setting webhook:", e)

if __name__ == '__main__':
    set_webhook()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
