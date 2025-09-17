from flask import Flask, request, jsonify
import requests
import os
import json
import re
from datetime import datetime, timedelta
import threading
import time
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Votre token de bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_states = {}
user_languages = {}
user_alarms = {}  # تخزين منبهات المستخدمين

# إنشاء مجدول للمنبهات
scheduler = BackgroundScheduler()
scheduler.start()

# Définition des claviers
def get_main_keyboard(lang='fr'):
    keyboards = {
        'fr': {
            'keyboard': [
                ['🔢 Réticulocytes', '🩸 Plaquettes'],
                ['🧪 Dilution', '⚙️ Paramètres'],
                ['ℹ️ Aide', '🔄 Langue', '⏰ Alarmes']
            ],
            'resize_keyboard': True
        },
        'en': {
            'keyboard': [
                ['🔢 Reticulocytes', '🩸 Platelets'],
                ['🧪 Dilution', '⚙️ Settings'],
                ['ℹ️ Help', '🔄 Language', '⏰ Alarms']
            ],
            'resize_keyboard': True
        },
        'ar': {
            'keyboard': [
                ['🔢 الخلايا الشبكية', '🩸 الصفائح الدموية'],
                ['🧪 التخفيف', '⚙️ الإعدادات'],
                ['ℹ️ المساعدة', '🔄 اللغة', '⏰ المنبهات']
            ],
            'resize_keyboard': True
        }
    }
    return keyboards.get(lang, keyboards['fr'])

def get_numeric_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '10'],
            ['15', '20', '25', '30', '50'],
            [cancel_text[lang]]
        ],
        'resize_keyboard': True
    }

def get_dilution_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [
            ['1/2', '1/5', '1/10'],
            ['1/20', '1/50', '1/100'],
            ['1/200', '1/500', '1/1000'],
            [cancel_text[lang]]
        ],
        'resize_keyboard': True
    }

def get_cancel_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [[cancel_text[lang]]],
        'resize_keyboard': True
    }

def get_language_keyboard():
    return {
        'keyboard': [
            ['🇫🇷 Français', '🇬🇧 English'],
            ['🇸🇦 العربية', '🔙 Retour']
        ],
        'resize_keyboard': True
    }

def get_settings_keyboard(lang='fr'):
    texts = {
        'fr': ['🔙 Retour', '🗑️ Effacer historique', '📊 Statistiques'],
        'en': ['🔙 Back', '🗑️ Clear history', '📊 Statistics'],
        'ar': ['🔙 رجوع', '🗑️ مسح السجل', '📊 الإحصائيات']
    }
    return {
        'keyboard': [[texts[lang][0]], [texts[lang][1]], [texts[lang][2]]],
        'resize_keyboard': True
    }

def get_alarm_keyboard(lang='fr'):
    texts = {
        'fr': ['🔙 Retour', '➕ Nouvelle alarme', '📋 Mes alarmes', '🗑️ Supprimer alarme'],
        'en': ['🔙 Back', '➕ New alarm', '📋 My alarms', '🗑️ Delete alarm'],
        'ar': ['🔙 رجوع', '➕ منبه جديد', '📋 منبهاتي', '🗑️ حذف منبه']
    }
    return {
        'keyboard': [[texts[lang][0]], [texts[lang][1]], [texts[lang][2]], [texts[lang][3]]],
        'resize_keyboard': True
    }

# Textes multilingues
TEXTS = {
    'fr': {
        'welcome': "👋 Bonjour ! Je suis votre assistant de laboratoire.\nChoisissez une option :",
        'reti_fields': "🔢 Combien de champs voulez-vous analyser pour les réticulocytes ?",
        'plaq_fields': "🩸 Combien de champs voulez-vous analyser pour les plaquettes ?",
        'dilution_prompt': "🧪 Entrez la dilution souhaitée (ex: 1/2, 1/10) :",
        'reti_count': "Entrez le nombre de réticulocytes dans le Champ {} :",
        'plaq_count': "Entrez le nombre de plaquettes dans le Champ {} :",
        'rbc_quarter': "Entrez le nombre de globules rouges dans le quart de Champ {} :",
        'gr_auto': "⚙️ Entrez le nombre de globules rouges auto (machine) :",
        'cancel': "❌ Opération annulée.",
        'invalid_number': "⚠️ Veuillez entrer un nombre valide.",
        'result_reti': "--- Résultat Réticulocytes ---\nTotal réticulocytes: {}\nMoyenne GR: {:.2f}\nTaux: {:.2f}%",
        'result_plaq': "--- Résultat Plaquettes ---\nMoyenne plaquettes: {:.2f}\nMoyenne GR: {:.2f}\nGR auto: {}\nRésultat: {:.2f}",
        'dilution_result': "🧪 Pour une dilution {}/{} :\n- Substance: {} partie(s)\n- Diluant: {} partie(s)",
        'quantity_prompt': "Entrez la quantité totale souhaitée :",
        'exact_volumes': "📊 Pour {} unité(s) :\n- Substance: {:.2f}\n- Diluant: {:.2f}",
        'help_text': """ℹ️ *AIDE - Commandes disponibles*

🔢 *Réticulocytes* : Calcul du taux de réticulocytes
🩸 *Plaquettes* : Calcul du nombre de plaquettes
🧪 *Dilution* : Préparation de dilutions
⚙️ *Paramètres* : Configuration du bot
🔄 *Langue* : Changer la langue
⏰ *Alarmes* : Gérer les alarmes

*Commandes rapides* :
/start - Démarrer le bot
/help - Afficher l'aide
/calc - Calcul réticulocytes
/plaquettes - Calcul plaquettes
/dilution - Préparation dilution
/alarm - Gérer les alarmes""",
        'settings': "⚙️ *Paramètres* :\n- Langue: Français\n- Historique: Activé",
        'stats': "📊 *Statistiques* :\n- Calculs effectués: {}\n- Dernier calcul: {}",
        'alarm_menu': "⏰ *Gestion des alarmes* :\nChoisissez une option :",
        'new_alarm_name': "Entrez un nom pour votre alarme :",
        'new_alarm_time': "Entrez l'heure pour l'alarme (format HH:MM) :",
        'alarm_added': "✅ Alarme '{}' programmée pour {}",
        'alarm_list': "📋 *Vos alarmes* :\n{}",
        'no_alarms': "Vous n'avez aucune alarme programmée.",
        'alarm_delete': "Entrez le nom de l'alarme à supprimer :",
        'alarm_deleted': "✅ Alarme '{}' supprimée.",
        'alarm_not_found': "❌ Aucune alarme nommée '{}' n'a été trouvée.",
        'invalid_time': "❌ Format d'heure invalide. Utilisez le format HH:MM."
    },
    'en': {
        'welcome': "👋 Hello! I'm your laboratory assistant.\nChoose an option:",
        'reti_fields': "🔢 How many fields do you want to analyze for reticulocytes?",
        'plaq_fields': "🩸 How many fields do you want to analyze for platelets?",
        'dilution_prompt': "🧪 Enter the desired dilution (ex: 1/2, 1/10):",
        'reti_count': "Enter the number of reticulocytes in Field {}:",
        'plaq_count': "Enter the number of platelets in Field {}:",
        'rbc_quarter': "Enter the number of red blood cells in quarter Field {}:",
        'gr_auto': "⚙️ Enter the automatic red blood cell count (machine):",
        'cancel': "❌ Operation cancelled.",
        'invalid_number': "⚠️ Please enter a valid number.",
        'result_reti': "--- Reticulocytes Result ---\nTotal reticulocytes: {}\nAverage RBC: {:.2f}\nRate: {:.2f}%",
        'result_plaq': "--- Platelets Result ---\nAverage platelets: {:.2f}\nAverage RBC: {:.2f}\nAuto RBC: {}\nResult: {:.2f}",
        'dilution_result': "🧪 For a {}/{} dilution:\n- Substance: {} part(s)\n- Diluent: {} part(s)",
        'quantity_prompt': "Enter the desired total quantity:",
        'exact_volumes': "📊 For {} unit(s):\n- Substance: {:.2f}\n- Diluent: {:.2f}",
        'help_text': """ℹ️ *HELP - Available commands*

🔢 *Reticulocytes* : Reticulocyte count calculation
🩸 *Platelets* : Platelet count calculation
🧪 *Dilution* : Dilution preparation
⚙️ *Settings* : Bot configuration
🔄 *Language* : Change language
⏰ *Alarms* : Manage alarms

*Quick commands* :
/start - Start bot
/help - Show help
/calc - Calculate reticulocytes
/plaquettes - Calculate platelets
/dilution - Prepare dilution
/alarm - Manage alarms""",
        'settings': "⚙️ *Settings* :\n- Language: English\n- History: Enabled",
        'stats': "📊 *Statistics* :\n- Calculations done: {}\n- Last calculation: {}",
        'alarm_menu': "⏰ *Alarm Management* :\nChoose an option:",
        'new_alarm_name': "Enter a name for your alarm:",
        'new_alarm_time': "Enter the time for the alarm (HH:MM format):",
        'alarm_added': "✅ Alarm '{}' scheduled for {}",
        'alarm_list': "📋 *Your Alarms* :\n{}",
        'no_alarms': "You have no alarms scheduled.",
        'alarm_delete': "Enter the name of the alarm to delete:",
        'alarm_deleted': "✅ Alarm '{}' deleted.",
        'alarm_not_found': "❌ No alarm named '{}' found.",
        'invalid_time': "❌ Invalid time format. Use HH:MM format."
    },
    'ar': {
        'welcome': "👋 مرحبًا! أنا مساعدك في المختبر.\nاختر خيارًا:",
        'reti_fields': "🔢 كم حقلًا تريد تحليله للخلايا الشبكية؟",
        'plaq_fields': "🩸 كم حقلًا تريد تحليله للصفائح الدموية؟",
        'dilution_prompt': "🧪 أدخل التخفيف المطلوب (مثال: 1/2, 1/10):",
        'reti_count': "أدخل عدد الخلايا الشبكية في الحقل {}:",
        'plaq_count': "أدخل عدد الصفائح الدموية في الحقل {}:",
        'rbc_quarter': "أدخل عدد كريات الدم الحمراء في ربع الحقل {}:",
        'gr_auto': "⚙️ أدخل عدد كريات الدم الحمراء التلقائي (الآلة):",
        'cancel': "❌ تم إلغاء العملية.",
        'invalid_number': "⚠️ الرجاء إدخال رقم صحيح.",
        'result_reti': "--- نتيجة الخلايا الشبكية ---\nالمجموع: {}\nمتوسط كريات الدم الحمراء: {:.2f}\nالنسبة: {:.2f}%",
        'result_plaq': "--- نتيجة الصفائح الدموية ---\nمتوسط الصفائح: {:.2f}\nمتوسط كريات الدم الحمراء: {:.2f}\nالعدد التلقائي: {}\nالنتيجة: {:.2f}",
        'dilution_result': "🧪 للتخفيف {}/{} :\n- المادة: {} جزء\n- المخفف: {} جزء",
        'quantity_prompt': "أدخل الكمية الإجمالية المطلوبة:",
        'exact_volumes': "📊 لكل {} وحدة:\n- المادة: {:.2f}\n- المخفف: {:.2f}",
        'help_text': """ℹ️ *المساعدة - الأوامر المتاحة*

🔢 *الخلايا الشبكية* : حساب نسبة الخلايا الشبكية
🩸 *الصفائح الدموية* : حساب عدد الصفائح الدموية
🧪 *التخفيف* : تحضير المحاليل المخففة
⚙️ *الإعدادات* : تكوين البوت
🔄 *اللغة* : تغيير اللغة
⏰ *المنبهات* : إدارة المنبهات

*أوامر سريعة* :
/start - بدء البوت
/help - عرض المساعدة
/calc - حساب الخلايا الشبكية
/plaquettes - حساب الصفائح الدموية
/dilution - تحضير التخفيف
/alarm - إدارة المنبهات""",
        'settings': "⚙️ *الإعدادات* :\n- اللغة: العربية\n- السجل: مفعل",
        'stats': "📊 *الإحصائيات* :\n- عدد العمليات الحسابية: {}\n- آخر عملية: {}",
        'alarm_menu': "⏰ *إدارة المنبهات* :\nاختر خيارًا:",
        'new_alarm_name': "أدخل اسمًا للمنبه:",
        'new_alarm_time': "أدخل وقت المنبه (صيغة ساعة:دقيقة):",
        'alarm_added': "✅ تمت برمجة المنبه '{}' لوقت {}",
        'alarm_list': "📋 *منبهاتك* :\n{}",
        'no_alarms': "ليس لديك أي منبهات مبرمجة.",
        'alarm_delete': "أدخل اسم المنبه الذي تريد حذفه:",
        'alarm_deleted': "✅ تم حذف المنبه '{}'.",
        'alarm_not_found': "❌ لم يتم العثور على منبه باسم '{}'.",
        'invalid_time': "❌ تنسيق وقت غير صالح. استخدم تنسيق ساعة:دقيقة."
    }
}

# Statistiques
calculations_history = []

# وظيفة تشغيل المنبه
def trigger_alarm(chat_id, alarm_name):
    lang = user_languages.get(chat_id, 'fr')
    message = f"⏰ *منبه*: {alarm_name}\nالوقت: {datetime.now().strftime('%H:%M')}"
    send_message(chat_id, message, get_main_keyboard(lang), parse_mode='Markdown')

@app.route('/')
def home():
    return "Le bot fonctionne correctement !"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        lang = user_languages.get(chat_id, 'fr')

        # Gestion des commandes textuelles et boutons
        if text == '/start' or text == '🔙 Retour' or text == '🔙 Back' or text == '🔙 رجوع':
            send_welcome_start(chat_id, lang)
            user_states[chat_id] = {'step': 0}
        
        elif text == '/help' or text == 'ℹ️ Aide' or text == 'ℹ️ Help' or text == 'ℹ️ المساعدة':
            send_message(chat_id, TEXTS[lang]['help_text'], get_main_keyboard(lang), parse_mode='Markdown')
        
        elif text == '/calc' or text == '🔢 Réticulocytes' or text == '🔢 Reticulocytes' or text == '🔢 الخلايا الشبكية':
            send_message(chat_id, TEXTS[lang]['reti_fields'], get_numeric_keyboard(lang))
            user_states[chat_id] = {'step': 50, 'type': 'reti', 'reti_counts': [], 'rbc_counts': [], 'nb_champs': None}
        
        elif text == '/plaquettes' or text == '🩸 Plaquettes' or text == '🩸 Platelets' or text == '🩸 الصفائح الدموية':
            send_message(chat_id, TEXTS[lang]['plaq_fields'], get_numeric_keyboard(lang))
            user_states[chat_id] = {'step': 100, 'type': 'plaq', 'plaq_counts': [], 'rbc_counts': [], 'gr_auto': None, 'nb_champs': None}
        
        elif text == '/dilution' or text == '🧪 Dilution' or text == '🧪 التخفيف':
            send_message(chat_id, TEXTS[lang]['dilution_prompt'], get_dilution_keyboard(lang))
            user_states[chat_id] = {'step': 400, 'type': 'dilution'}
        
        elif text == '/alarm' or text == '⏰ Alarmes' or text == '⏰ Alarms' or text == '⏰ المنبهات':
            send_message(chat_id, TEXTS[lang]['alarm_menu'], get_alarm_keyboard(lang), parse_mode='Markdown')
            user_states[chat_id] = {'step': 0}
        
        elif text == '⚙️ Paramètres' or text == '⚙️ Settings' or text == '⚙️ الإعدادات':
            send_message(chat_id, TEXTS[lang]['settings'], get_settings_keyboard(lang), parse_mode='Markdown')
        
        elif text == '🔄 Langue' or text == '🔄 Language' or text == '🔄 اللغة':
            send_message(chat_id, "🌍 Choose your language / اختر لغتك:", get_language_keyboard())
        
        elif text == '🇫🇷 Français':
            user_languages[chat_id] = 'fr'
            send_message(chat_id, "✅ Langue changée en Français", get_main_keyboard('fr'))
        
        elif text == '🇬🇧 English':
            user_languages[chat_id] = 'en'
            send_message(chat_id, "✅ Language changed to English", get_main_keyboard('en'))
        
        elif text == '🇸🇦 العربية':
            user_languages[chat_id] = 'ar'
            send_message(chat_id, "✅ تم تغيير اللغة إلى العربية", get_main_keyboard('ar'))
        
        elif text == '📊 Statistiques' or text == '📊 Statistics' or text == '📊 الإحصائيات':
            stats_text = TEXTS[lang]['stats'].format(len(calculations_history), 
                                                   calculations_history[-1]['type'] if calculations_history else 'None')
            send_message(chat_id, stats_text, get_main_keyboard(lang), parse_mode='Markdown')
        
        elif text == '➕ Nouvelle alarme' or text == '➕ New alarm' or text == '➕ منبه جديد':
            send_message(chat_id, TEXTS[lang]['new_alarm_name'], get_cancel_keyboard(lang))
            user_states[chat_id] = {'step': 600, 'type': 'alarm'}
        
        elif text == '📋 Mes alarmes' or text == '📋 My alarms' or text == '📋 منبهاتي':
            if chat_id in user_alarms and user_alarms[chat_id]:
                alarms_list = "\n".join([f"• {name} - {time}" for name, time in user_alarms[chat_id].items()])
                send_message(chat_id, TEXTS[lang]['alarm_list'].format(alarms_list), get_alarm_keyboard(lang), parse_mode='Markdown')
            else:
                send_message(chat_id, TEXTS[lang]['no_alarms'], get_alarm_keyboard(lang))
        
        elif text == '🗑️ Supprimer alarme' or text == '🗑️ Delete alarm' or text == '🗑️ حذف منبه':
            send_message(chat_id, TEXTS[lang]['alarm_delete'], get_cancel_keyboard(lang))
            user_states[chat_id] = {'step': 700, 'type': 'alarm_delete'}
        
        elif text.lower() in ['annuler', 'cancel', 'إلغاء']:
            send_message(chat_id, TEXTS[lang]['cancel'], get_main_keyboard(lang))
            user_states[chat_id] = {'step': 0}
        
        elif chat_id in user_states:
            handle_input(chat_id, text, lang)
    
    return jsonify({'status': 'ok'})

# -------------------- Gestion des inputs --------------------

def handle_input(chat_id, text, lang):
    state = user_states[chat_id]

    try:
        if state.get('type') != 'dilution' and state.get('type') != 'alarm' and state.get('type') != 'alarm_delete':
            value = float(text) if '.' in text else int(text)
            if value < 0:
                send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))
                return
        else:
            value = text

        if state.get('type') == 'reti':
            handle_reti(chat_id, value, lang)
        elif state.get('type') == 'plaq':
            handle_plaquettes(chat_id, value, lang)
        elif state.get('type') == 'dilution':
            handle_dilution(chat_id, value, lang)
        elif state.get('type') == 'alarm':
            handle_alarm(chat_id, text, lang)
        elif state.get('type') == 'alarm_delete':
            handle_alarm_delete(chat_id, text, lang)
    
    except ValueError:
        send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))

# -------------------- Réticulocytes --------------------

def handle_reti(chat_id, value, lang):
    state = user_states[chat_id]

    if state['step'] == 50:
        state['nb_champs'] = value
        send_message(chat_id, TEXTS[lang]['reti_count'].format(1), get_numeric_keyboard(lang))
        state['step'] = 51
        return

    if 51 <= state['step'] < 51 + state['nb_champs']:
        state['reti_counts'].append(value)
        champ_actuel = len(state['reti_counts'])
        if len(state['reti_counts']) < state['nb_champs']:
            send_message(chat_id, TEXTS[lang]['reti_count'].format(champ_actuel + 1), get_numeric_keyboard(lang))
            state['step'] += 1
        else:
            send_message(chat_id, TEXTS[lang]['rbc_quarter'].format(1), get_numeric_keyboard(lang))
            state['step'] = 200
        return

    if 200 <= state['step'] <= 202:
        state['rbc_counts'].append(value)
        if state['step'] < 202:
            champ = state['step'] - 199
            send_message(chat_id, TEXTS[lang]['rbc_quarter'].format(champ + 1), get_numeric_keyboard(lang))
            state['step'] += 1
        else:
            reti_total = sum(state['reti_counts'])
            rbc_total = sum([x*4 for x in state['rbc_counts']]) / 3 * state['nb_champs']
            taux = (reti_total / rbc_total) * 100
            
            # Enregistrer dans l'historique
            calculations_history.append({
                'type': 'reticulocytes',
                'result': taux,
                'timestamp': datetime.now().isoformat()
            })
            
            message = TEXTS[lang]['result_reti'].format(reti_total, rbc_total, taux)
            send_message(chat_id, message, get_main_keyboard(lang))
            send_welcome_end(chat_id, lang)
            user_states[chat_id] = {'step': 0}

# -------------------- Plaquettes --------------------

def handle_plaquettes(chat_id, value, lang):
    state = user_states[chat_id]

    if state['step'] == 100:
        state['nb_champs'] = value
        send_message(chat_id, TEXTS[lang]['plaq_count'].format(1), get_numeric_keyboard(lang))
        state['step'] = 101
        return

    if 101 <= state['step'] < 101 + state['nb_champs']:
        state['plaq_counts'].append(value)
        champ_actuel = len(state['plaq_counts'])
        if len(state['plaq_counts']) < state['nb_champs']:
            send_message(chat_id, TEXTS[lang]['plaq_count'].format(champ_actuel + 1), get_numeric_keyboard(lang))
            state['step'] += 1
        else:
            send_message(chat_id, TEXTS[lang]['rbc_quarter'].format(1), get_numeric_keyboard(lang))
            state['step'] = 300
        return

    if 300 <= state['step'] <= 302:
        state['rbc_counts'].append(value)
        if state['step'] < 302:
            champ = state['step'] - 299
            send_message(chat_id, TEXTS[lang]['rbc_quarter'].format(champ + 1), get_numeric_keyboard(lang))
            state['step'] += 1
        else:
            send_message(chat_id, TEXTS[lang]['gr_auto'], get_numeric_keyboard(lang))
            state['step'] = 303
        return

    if state['step'] == 303:
        state['gr_auto'] = value
        plaq_moy = sum(state['plaq_counts']) / state['nb_champs']
        avg_rbc = sum([x*4 for x in state['rbc_counts']]) / 3
        result = (state['gr_auto'] * plaq_moy) / avg_rbc
        
        # Enregistrer dans l'historique
        calculations_history.append({
            'type': 'platelets',
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
        
        message = TEXTS[lang]['result_plaq'].format(plaq_moy, avg_rbc, state['gr_auto'], result)
        send_message(chat_id, message, get_main_keyboard(lang))
        send_welcome_end(chat_id, lang)
        user_states[chat_id] = {'step': 0}

# -------------------- Dilution --------------------

def handle_dilution(chat_id, text, lang):
    state = user_states[chat_id]

    try:
        if state['step'] == 400:
            if '/' in text:
                numer, denom = map(int, text.split('/'))
                if numer <= 0 or denom <= 0 or numer > denom:
                    raise ValueError
                
                message = TEXTS[lang]['dilution_result'].format(numer, denom, numer, denom - numer)
                send_message(chat_id, message, get_main_keyboard(lang))
                
                # Demander pour les volumes exacts
                send_message(chat_id, TEXTS[lang]['quantity_prompt'], get_cancel_keyboard(lang))
                state['step'] = 401
                state['last_dilution'] = text
            else:
                send_message(chat_id, TEXTS[lang]['invalid_number'], get_dilution_keyboard(lang))
        
        elif state['step'] == 401:
            if text.lower() in ['annuler', 'cancel', 'إلغاء']:
                send_welcome_end(chat_id, lang)
                user_states[chat_id] = {'step': 0}
            else:
                quantite = float(text)
                numer, denom = map(int, state.get('last_dilution', '1/2').split('/'))
                part_substance = (numer/denom) * quantite
                part_diluant = quantite - part_substance
                
                message = TEXTS[lang]['exact_volumes'].format(quantite, part_substance, part_diluant)
                send_message(chat_id, message, get_main_keyboard(lang))
                
                # Enregistrer dans l'historique
                calculations_history.append({
                    'type': 'dilution',
                    'result': f"{numer}/{denom}",
                    'timestamp': datetime.now().isoformat()
                })
                
                send_welcome_end(chat_id, lang)
                user_states[chat_id] = {'step': 0}
    
    except (ValueError, AttributeError):
        send_message(chat_id, TEXTS[lang]['invalid_number'], get_dilution_keyboard(lang))

# -------------------- Alarmes --------------------

def handle_alarm(chat_id, text, lang):
    state = user_states[chat_id]
    
    if state['step'] == 600:
        # Étape 1: Nom de l'alarme
        state['alarm_name'] = text
        send_message(chat_id, TEXTS[lang]['new_alarm_time'], get_cancel_keyboard(lang))
        state['step'] = 601
    
    elif state['step'] == 601:
        # Étape 2: Heure de l'alarme
        if re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', text):
            alarm_time = text
            now = datetime.now()
            alarm_datetime = datetime.strptime(f"{now.date()} {alarm_time}", "%Y-%m-%d %H:%M")
            
            # Si l'heure est déjà passée aujourd'hui, programmer pour demain
            if alarm_datetime < now:
                alarm_datetime += timedelta(days=1)
            
            # Calculer le délai en secondes
            delay = (alarm_datetime - now).total_seconds()
            
            # Programmer l'alarme
            scheduler.add_job(
                trigger_alarm,
                'date',
                run_date=alarm_datetime,
                args=[chat_id, state['alarm_name']],
                id=f"alarm_{chat_id}_{state['alarm_name']}"
            )
            
            # Stocker l'alarme
            if chat_id not in user_alarms:
                user_alarms[chat_id] = {}
            user_alarms[chat_id][state['alarm_name']] = alarm_time
            
            send_message(chat_id, TEXTS[lang]['alarm_added'].format(state['alarm_name'], alarm_time), get_alarm_keyboard(lang))
            user_states[chat_id] = {'step': 0}
        else:
            send_message(chat_id, TEXTS[lang]['invalid_time'], get_cancel_keyboard(lang))

def handle_alarm_delete(chat_id, text, lang):
    if chat_id in user_alarms and text in user_alarms[chat_id]:
        # Supprimer l'alarme du planificateur
        try:
            scheduler.remove_job(f"alarm_{chat_id}_{text}")
        except:
            pass
        
        # Supprimer l'alarme de la liste
        del user_alarms[chat_id][text]
        
        # Si l'utilisateur n'a plus d'alarmes, supprimer sa liste
        if not user_alarms[chat_id]:
            del user_alarms[chat_id]
        
        send_message(chat_id, TEXTS[lang]['alarm_deleted'].format(text), get_alarm_keyboard(lang))
    else:
        send_message(chat_id, TEXTS[lang]['alarm_not_found'].format(text), get_alarm_keyboard(lang))
    
    user_states[chat_id] = {'step': 0}

# -------------------- Messages --------------------

def send_welcome_start(chat_id, lang='fr'):
    send_message(chat_id, TEXTS[lang]['welcome'], get_main_keyboard(lang))

def send_welcome_end(chat_id, lang='fr'):
    message = {
        'fr': "✅ Calcul terminé !\nChoisissez une autre option :",
        'en': "✅ Calculation completed!\nChoose another option:",
        'ar': "✅ اكتمل الحساب!\nاختر خيارًا آخر:"
    }
    send_message(chat_id, message.get(lang, "✅ Done!"), get_main_keyboard(lang))

# -------------------- Envoi des messages --------------------

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {
        "chat_id": chat_id, 
        "text": text
    }
    
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    
    if parse_mode:
        data["parse_mode"] = parse_mode
    
    try:
        requests.post(url, json=data, timeout=10)
    except requests.exceptions.RequestException:
        pass 

def set_webhook():
    """تعيين الويب هوك للبوت"""
    webhook_url = os.environ.get('WEBHOOK_URL') + '/webhook'
    url = f"{TELEGRAM_API_URL}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(url)
        print(f"Webhook set: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error setting webhook: {e}")

if __name__ == '__main__':
    # تعيين الويب هوك عند التشغيل
    set_webhook()
    
    # تشغيل التطبيق
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
