from flask import Flask, request, jsonify
import requests
import os
import json
import re
from datetime import datetime, timedelta
import threading
import time
from typing import Dict, List, Any

app = Flask(__name__)

# Votre token de bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_states = {}
user_languages = {}
user_alarms = {}  # تخزين المنبهات للمستخدمين

# إضافة متغير للتحقق من المنبهات
alarm_check_thread = None
alarm_check_running = True

# Définition des claviers
def get_main_keyboard(lang='fr'):
    keyboards = {
        'fr': {
            'keyboard': [
                ['🔢 Réticulocytes', '🩸 Plaquettes'],
                ['🧪 Dilution', '⚙️ Paramètres'],
                ['ℹ️ Aide', '🔄 Langue'],
                ['⏰ Horloge', '🔔 Mes Alarmes']  # إضافة أزرار الساعة والمنبهات
            ],
            'resize_keyboard': True
        },
        'en': {
            'keyboard': [
                ['🔢 Reticulocytes', '🩸 Platelets'],
                ['🧪 Dilution', '⚙️ Settings'],
                ['ℹ️ Help', '🔄 Language'],
                ['⏰ Clock', '🔔 My Alarms']  # إضافة أزرار الساعة والمنبهات
            ],
            'resize_keyboard': True
        },
        'ar': {
            'keyboard': [
                ['🔢 الخلايا الشبكية', '🩸 الصفائح الدموية'],
                ['🧪 التخفيف', '⚙️ الإعدادات'],
                ['ℹ️ المساعدة', '🔄 اللغة'],
                ['⏰ الساعة', '🔔 منبهاتي']  # إضافة أزرار الساعة والمنبهات
            ],
            'resize_keyboard': True
        }
    }
    return keyboards.get(lang, keyboards['fr'])

def get_alarm_keyboard(lang='fr'):
    texts = {
        'fr': ['➕ Nouvelle alarme', '🗑️ Supprimer alarme', '📋 Liste alarmes', '🔙 Retour'],
        'en': ['➕ New alarm', '🗑️ Delete alarm', '📋 List alarms', '🔙 Back'],
        'ar': ['➕ منبه جديد', '🗑️ حذف المنبه', '📋 قائمة المنبهات', '🔙 رجوع']
    }
    return {
        'keyboard': [
            [texts[lang][0], texts[lang][1]],
            [texts[lang][2], texts[lang][3]]
        ],
        'resize_keyboard': True
    }

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

def get_time_selection_keyboard(lang='fr'):
    cancel_text = {'fr': 'Annuler', 'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [
            ['00', '01', '02', '03', '04', '05'],
            ['06', '07', '08', '09', '10', '11'],
            ['12', '13', '14', '15', '16', '17'],
            ['18', '19', '20', '21', '22', '23'],
            ['30', '45', cancel_text[lang]]
        ],
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
⏰ *Horloge* : Afficher l'heure et gérer les alarmes
🔔 *Mes Alarmes* : Gérer vos alarmes personnalisées

*Commandes rapides* :
/start - Démarrer le bot
/help - Afficher l'aide
/calc - Calcul réticulocytes
/plaquettes - Calcul plaquettes
/dilution - Préparation dilution
/time - Afficher l'heure actuelle
/alarms - Gérer les alarmes""",
        'settings': "⚙️ *Paramètres* :\n- Langue: Français\n- Historique: Activé",
        'stats': "📊 *Statistiques* :\n- Calculs effectués: {}\n- Dernier calcul: {}",
        'current_time': "⏰ Heure actuelle: {}",
        'alarm_menu': "🔔 *Gestion des alarmes* :\nChoisissez une option :",
        'new_alarm_name': "Entrez un nom pour votre nouvelle alarme :",
        'new_alarm_time': "Entrez l'heure pour l'alarme (format HH:MM) :",
        'alarm_added': "✅ Alarme '{}' programmée pour {}",
        'alarm_deleted': "✅ Alarme '{}' supprimée",
        'no_alarms': "📭 Vous n'avez aucune alarme programmée",
        'alarm_list': "📋 Vos alarmes :\n{}",
        'alarm_item': "• {} - {}\n",
        'select_alarm_to_delete': "Sélectionnez l'alarme à supprimer :",
        'invalid_time': "⚠️ Format d'heure invalide. Utilisez HH:MM",
        'alarm_triggered': "🔔 ALARME: {}"
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
⏰ *Clock* : Show current time and manage alarms
🔔 *My Alarms* : Manage your custom alarms

*Quick commands* :
/start - Start bot
/help - Show help
/calc - Calculate reticulocytes
/plaquettes - Calculate platelets
/dilution - Prepare dilution
/time - Show current time
/alarms - Manage alarms""",
        'settings': "⚙️ *Settings* :\n- Language: English\n- History: Enabled",
        'stats': "📊 *Statistics* :\n- Calculations done: {}\n- Last calculation: {}",
        'current_time': "⏰ Current time: {}",
        'alarm_menu': "🔔 *Alarm Management* :\nChoose an option:",
        'new_alarm_name': "Enter a name for your new alarm:",
        'new_alarm_time': "Enter the time for the alarm (HH:MM format):",
        'alarm_added': "✅ Alarm '{}' set for {}",
        'alarm_deleted': "✅ Alarm '{}' deleted",
        'no_alarms': "📭 You have no alarms set",
        'alarm_list': "📋 Your alarms:\n{}",
        'alarm_item': "• {} - {}\n",
        'select_alarm_to_delete': "Select the alarm to delete:",
        'invalid_time': "⚠️ Invalid time format. Use HH:MM",
        'alarm_triggered': "🔔 ALARM: {}"
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
⏰ *الساعة* : عرض الوقت الحالي وإدارة المنبهات
🔔 *منبهاتي* : إدارة المنبهات المخصصة

*أوامر سريعة* :
/start - بدء البوت
/help - عرض المساعدة
/calc - حساب الخلايا الشبكية
/plaquettes - حساب الصفائح الدموية
/dilution - تحضير التخفيف
/time - عرض الوقت الحالي
/alarms - إدارة المنبهات""",
        'settings': "⚙️ *الإعدادات* :\n- اللغة: العربية\n- السجل: مفعل",
        'stats': "📊 *الإحصائيات* :\n- عدد العمليات الحسابية: {}\n- آخر عملية: {}",
        'current_time': "⏰ الوقت الحالي: {}",
        'alarm_menu': "🔔 *إدارة المنبهات* :\nاختر خيارًا:",
        'new_alarm_name': "أدخل اسمًا للمنبه الجديد:",
        'new_alarm_time': "أدخل وقت المنبه (صيغة س:د):",
        'alarm_added': "✅ تم ضبط المنبه '{}' لـ {}",
        'alarm_deleted': "✅ تم حذف المنبه '{}'",
        'no_alarms': "📭 ليس لديك أي منبهات مضبوطة",
        'alarm_list': "📋 منبهاتك:\n{}",
        'alarm_item': "• {} - {}\n",
        'select_alarm_to_delete': "اختر المنبه الذي تريد حذفه:",
        'invalid_time': "⚠️ تنسيق وقت غير صحيح. استخدم س:د",
        'alarm_triggered': "🔔 منبه: {}"
    }
}

# Statistiques
calculations_history = []

# وظيفة للتحقق من المنبهات
def check_alarms():
    while alarm_check_running:
        try:
            current_time = datetime.now().strftime("%H:%M")
            for chat_id, alarms in list(user_alarms.items()):
                for alarm_name, alarm_time in list(alarms.items()):
                    if alarm_time == current_time:
                        lang = user_languages.get(chat_id, 'fr')
                        message = TEXTS[lang]['alarm_triggered'].format(alarm_name)
                        send_message(chat_id, message, get_main_keyboard(lang))
                        # إزالة المنبه بعد تشغيله (للتشغيل لمرة واحدة)
                        del user_alarms[chat_id][alarm_name]
            time.sleep(30)  # التحقق كل 30 ثانية
        except Exception as e:
            print(f"Error in alarm check: {e}")
            time.sleep(60)

# بدء التحقق من المنبهات عند تشغيل التطبيق
alarm_check_thread = threading.Thread(target=check_alarms)
alarm_check_thread.daemon = True
alarm_check_thread.start()

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
        
        # إضافة أوامر الساعة والمنبهات
        elif text == '/time' or text == '⏰ Horloge' or text == '⏰ Clock' or text == '⏰ الساعة':
            current_time = datetime.now().strftime("%H:%M:%S")
            send_message(chat_id, TEXTS[lang]['current_time'].format(current_time), get_main_keyboard(lang))
        
        elif text == '/alarms' or text == '🔔 Mes Alarmes' or text == '🔔 My Alarms' or text == '🔔 منبهاتي':
            send_message(chat_id, TEXTS[lang]['alarm_menu'], get_alarm_keyboard(lang), parse_mode='Markdown')
            user_states[chat_id] = {'step': 500, 'type': 'alarms'}
        
        elif text.lower() in ['annuler', 'cancel', 'إلغاء']:
            send_message(chat_id, TEXTS[lang]['cancel'], get_main_keyboard(lang))
            user_states[chat_id] = {'step': 0}
        
        elif chat_id in user_states:
            handle_input(chat_id, text, lang)
        else:
            # إذا لم يكن هناك حالة، نعرض القائمة الرئيسية
            send_welcome_start(chat_id, lang)
            user_states[chat_id] = {'step': 0}
    
    return jsonify({'status': 'ok'})

# -------------------- Gestion des inputs --------------------

def handle_input(chat_id, text, lang):
    state = user_states[chat_id]

    try:
        if state.get('type') == 'alarms':
            handle_alarms(chat_id, text, lang)
        elif state.get('type') != 'dilution':
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
    
    except ValueError:
        send_message(chat_id, TEXTS[lang]['invalid_number'], get_numeric_keyboard(lang))

# -------------------- Gestion des alarmes --------------------

def handle_alarms(chat_id, text, lang):
    state = user_states[chat_id]
    
    if text == '➕ Nouvelle alarme' or text == '➕ New alarm' or text == '➕ منبه جديد':
        send_message(chat_id, TEXTS[lang]['new_alarm_name'], get_cancel_keyboard(lang))
        state['step'] = 501  # انتظار اسم المنبه
    
    elif text == '🗑️ Supprimer alarme' or text == '🗑️ Delete alarm' or text == '🗑️ حذف المنبه':
        if chat_id not in user_alarms or not user_alarms[chat_id]:
            send_message(chat_id, TEXTS[lang]['no_alarms'], get_alarm_keyboard(lang))
        else:
            alarm_list = "\n".join([f"{i+1}. {name} - {time}" for i, (name, time) in enumerate(user_alarms[chat_id].items())])
            send_message(chat_id, TEXTS[lang]['select_alarm_to_delete'] + "\n" + alarm_list, get_cancel_keyboard(lang))
            state['step'] = 503  # انتظار اختيار المنبه للحذف
    
    elif text == '📋 Liste alarmes' or text == '📋 List alarms' or text == '📋 قائمة المنبهات':
        if chat_id not in user_alarms or not user_alarms[chat_id]:
            send_message(chat_id, TEXTS[lang]['no_alarms'], get_alarm_keyboard(lang))
        else:
            alarm_list = ""
            for name, time in user_alarms[chat_id].items():
                alarm_list += TEXTS[lang]['alarm_item'].format(name, time)
            send_message(chat_id, TEXTS[lang]['alarm_list'].format(alarm_list), get_alarm_keyboard(lang))
    
    elif state['step'] == 501:  # انتظار اسم المنبه
        state['new_alarm_name'] = text
        send_message(chat_id, TEXTS[lang]['new_alarm_time'], get_time_selection_keyboard(lang))
        state['step'] = 502  # انتظار وقت المنبه
    
    elif state['step'] == 502:  # انتظار وقت المنبه
        # التحقق من صيغة الوقت
        if re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', text):
            if chat_id not in user_alarms:
                user_alarms[chat_id] = {}
            user_alarms[chat_id][state['new_alarm_name']] = text
            send_message(chat_id, TEXTS[lang]['alarm_added'].format(state['new_alarm_name'], text), get_alarm_keyboard(lang))
            state['step'] = 500  # العودة إلى قائمة المنبهات
        else:
            send_message(chat_id, TEXTS[lang]['invalid_time'], get_time_selection_keyboard(lang))
    
    elif state['step'] == 503:  # انتظار اختيار المنبه للحذف
        try:
            alarm_index = int(text) - 1
            alarm_name = list(user_alarms[chat_id].keys())[alarm_index]
            del user_alarms[chat_id][alarm_name]
            send_message(chat_id, TEXTS[lang]['alarm_deleted'].format(alarm_name), get_alarm_keyboard(lang))
            state['step'] = 500  # العودة إلى قائمة المنبهات
        except (ValueError, IndexError):
            send_message(chat_id, TEXTS[lang]['invalid_number'], get_alarm_keyboard(lang))

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
