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
active_alarms = {}  # المنبهات النشطة التي ترن حالياً

# إضافة متغير للتحقق من المنبهات
alarm_check_thread = None
alarm_check_running = True

# Définition des claviers
def get_main_keyboard(lang='en'):
    keyboards = {
        'en': {
            'keyboard': [
                ['⏰ Current Time', '🔔 My Alarms'],
                ['⚙️ Settings', '🔄 Language']
            ],
            'resize_keyboard': True
        },
        'ar': {
            'keyboard': [
                ['⏰ الوقت الحالي', '🔔 منبهاتي'],
                ['⚙️ الإعدادات', '🔄 اللغة']
            ],
            'resize_keyboard': True
        }
    }
    return keyboards.get(lang, keyboards['en'])

def get_alarm_keyboard(lang='en'):
    texts = {
        'en': ['➕ New alarm', '🗑️ Delete alarm', '📋 List alarms', '🔙 Back', '🔕 Stop alarm'],
        'ar': ['➕ منبه جديد', '🗑️ حذف المنبه', '📋 قائمة المنبهات', '🔙 رجوع', '🔕 إيقاف المنبه']
    }
    return {
        'keyboard': [
            [texts[lang][0], texts[lang][1]],
            [texts[lang][2], texts[lang][3]],
            [texts[lang][4]]
        ],
        'resize_keyboard': True
    }

def get_stop_alarm_keyboard(lang='en'):
    stop_text = {'en': '🔕 Stop', 'ar': '🔕 إيقاف'}
    return {
        'keyboard': [[stop_text[lang]]],
        'resize_keyboard': True
    }

def get_cancel_keyboard(lang='en'):
    cancel_text = {'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [[cancel_text[lang]]],
        'resize_keyboard': True
    }

def get_time_selection_keyboard(lang='en'):
    cancel_text = {'en': 'Cancel', 'ar': 'إلغاء'}
    return {
        'keyboard': [
            ['00', '01', '02', '03', '04', '05'],
            ['06', '07', '08', '09', '10', '11'],
            ['12', '13', '14', '15', '16', '17'],
            ['18', '19', '20', '21', '22', '23'],
            ['00', '15', '30', '45', cancel_text[lang]]
        ],
        'resize_keyboard': True
    }

def get_language_keyboard():
    return {
        'keyboard': [
            ['🇬🇧 English', '🇸🇦 العربية'],
            ['🔙 Back']
        ],
        'resize_keyboard': True
    }

def get_settings_keyboard(lang='en'):
    texts = {
        'en': ['🔙 Back', '🗑️ Clear all alarms'],
        'ar': ['🔙 رجوع', '🗑️ مسح جميع المنبهات']
    }
    return {
        'keyboard': [[texts[lang][0]], [texts[lang][1]]],
        'resize_keyboard': True
    }

# Textes multilingues
TEXTS = {
    'en': {
        'welcome': "⏰ Welcome to your Alarm Bot!\nChoose an option:",
        'cancel': "❌ Operation cancelled.",
        'invalid_number': "⚠️ Please enter a valid number.",
        'help_text': """🔔 *ALARM BOT - Available commands*

⏰ *Current Time* : Show current time
🔔 *My Alarms* : Manage your alarms
⚙️ *Settings* : Bot configuration
🔄 *Language* : Change language

*Quick commands* :
/start - Start bot
/help - Show help
/time - Show current time
/alarms - Manage alarms
/stop_alarm - Stop active alarm""",
        'settings': "⚙️ *Settings* :\n- Language: English\n- Active alarms: {}",
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
        'invalid_time': "⚠️ Invalid time format. Use HH:MM (24h format)",
        'alarm_triggered': "🔔 ALARM: {}",
        'alarm_stopped': "✅ Alarm stopped",
        'no_active_alarm': "ℹ️ No active alarm to stop",
        'alarm_ringing': "🔔🔔🔔 ALARM RINGING: {} - Type /stop_alarm to stop",
        'all_alarms_cleared': "✅ All alarms have been cleared",
        'confirm_clear_all': "⚠️ Are you sure you want to delete ALL alarms? This cannot be undone. Type 'YES' to confirm:"
    },
    'ar': {
        'welcome': "⏰ مرحبًا بك في بوت المنبهات!\nاختر خيارًا:",
        'cancel': "❌ تم إلغاء العملية.",
        'invalid_number': "⚠️ الرجاء إدخال رقم صحيح.",
        'help_text': """🔔 *بوت المنبهات - الأوامر المتاحة*

⏰ *الوقت الحالي* : عرض الوقت الحالي
🔔 *منبهاتي* : إدارة المنبهات
⚙️ *الإعدادات* : تكوين البوت
🔄 *اللغة* : تغيير اللغة

*أوامر سريعة* :
/start - بدء البوت
/help - عرض المساعدة
/time - عرض الوقت الحالي
/alarms - إدارة المنبهات
/stop_alarm - إيقاف المنبه النشط""",
        'settings': "⚙️ *الإعدادات* :\n- اللغة: العربية\n- المنبهات النشطة: {}",
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
        'invalid_time': "⚠️ تنسيق وقت غير صحيح. استخدم س:د (توقيت 24 ساعة)",
        'alarm_triggered': "🔔 منبه: {}",
        'alarm_stopped': "✅ تم إيقاف المنبه",
        'no_active_alarm': "ℹ️ لا يوجد منبه نشط لإيقافه",
        'alarm_ringing': "🔔🔔🔔 منبه نشط: {} - اكتب /stop_alarm للإيقاف",
        'all_alarms_cleared': "✅ تم مسح جميع المنبهات",
        'confirm_clear_all': "⚠️ هل أنت متأكد أنك تريد حذف جميع المنبهات؟ لا يمكن التراجع عن هذا الإجراء. اكتب 'نعم' للتأكيد:"
    }
}

# وظيفة للتحقق من المنبهات
def check_alarms():
    while alarm_check_running:
        try:
            current_time = datetime.now().strftime("%H:%M")
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            for chat_id, alarms in list(user_alarms.items()):
                for alarm_name, alarm_data in list(alarms.items()):
                    alarm_time = alarm_data['time']
                    last_triggered = alarm_data.get('last_triggered', '')
                    
                    # التحقق إذا حان وقت المنبه ولم يتم تشغيله اليوم
                    if (alarm_time == current_time and 
                        last_triggered != current_date and
                        chat_id not in active_alarms):
                        
                        # تحديث وقت التشغيل الأخير
                        user_alarms[chat_id][alarm_name]['last_triggered'] = current_date
                        
                        # بدء المنبه
                        active_alarms[chat_id] = {
                            'name': alarm_name,
                            'start_time': datetime.now(),
                            'stop_requested': False
                        }
                        
                        lang = user_languages.get(chat_id, 'en')
                        message = TEXTS[lang]['alarm_triggered'].format(alarm_name)
                        send_message(chat_id, message, get_stop_alarm_keyboard(lang))
                        
                        # بدء الخيط الذي سيرسل إشعارات متكررة
                        alarm_thread = threading.Thread(target=ring_alarm, args=(chat_id, alarm_name, lang))
                        alarm_thread.daemon = True
                        alarm_thread.start()
            
            time.sleep(10)  # التحقق كل 10 ثواني للدقة
        except Exception as e:
            print(f"Error in alarm check: {e}")
            time.sleep(30)

# وظيفة لجعل المنبه يرن بشكل متكرر
def ring_alarm(chat_id, alarm_name, lang):
    try:
        start_time = datetime.now()
        max_duration = 300  # الحد الأقصى 5 دقائق
        
        while (chat_id in active_alarms and 
               not active_alarms[chat_id].get('stop_requested', False) and
               (datetime.now() - start_time).seconds < max_duration):
            
            message = TEXTS[lang]['alarm_ringing'].format(alarm_name)
            send_message(chat_id, message, get_stop_alarm_keyboard(lang))
            time.sleep(15)  # إرسال إشعار كل 15 ثانية
        
        # تنظيف بعد إيقاف المنبه
        if chat_id in active_alarms:
            del active_alarms[chat_id]
            
    except Exception as e:
        print(f"Error in ring_alarm: {e}")
        if chat_id in active_alarms:
            del active_alarms[chat_id]

# بدء التحقق من المنبهات عند تشغيل التطبيق
alarm_check_thread = threading.Thread(target=check_alarms)
alarm_check_thread.daemon = True
alarm_check_thread.start()

@app.route('/')
def home():
    return "Alarm Bot is running correctly!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        lang = user_languages.get(chat_id, 'en')

        # Gestion des commandes textuelles et boutons
        if text == '/start' or text == '🔙 Back' or text == '🔙 رجوع':
            send_welcome_start(chat_id, lang)
            user_states[chat_id] = {'step': 0}
        
        elif text == '/help' or text == 'ℹ️ Help' or text == 'ℹ️ المساعدة':
            send_message(chat_id, TEXTS[lang]['help_text'], get_main_keyboard(lang), parse_mode='Markdown')
        
        elif text == '⚙️ Settings' or text == '⚙️ الإعدادات':
            active_count = sum(1 for chat in active_alarms.values() if not chat.get('stop_requested', False))
            settings_text = TEXTS[lang]['settings'].format(active_count)
            send_message(chat_id, settings_text, get_settings_keyboard(lang), parse_mode='Markdown')
            user_states[chat_id] = {'step': 600, 'type': 'settings'}
        
        elif text == '🔄 Language' or text == '🔄 اللغة':
            send_message(chat_id, "🌍 Choose your language / اختر لغتك:", get_language_keyboard())
        
        elif text == '🇬🇧 English':
            user_languages[chat_id] = 'en'
            send_message(chat_id, "✅ Language changed to English", get_main_keyboard('en'))
        
        elif text == '🇸🇦 العربية':
            user_languages[chat_id] = 'ar'
            send_message(chat_id, "✅ تم تغيير اللغة إلى العربية", get_main_keyboard('ar'))
        
        # إضافة أوامر الساعة والمنبهات
        elif text == '/time' or text == '⏰ Current Time' or text == '⏰ الوقت الحالي':
            current_time = datetime.now().strftime("%H:%M:%S")
            send_message(chat_id, TEXTS[lang]['current_time'].format(current_time), get_main_keyboard(lang))
        
        elif text == '/alarms' or text == '🔔 My Alarms' or text == '🔔 منبهاتي':
            send_message(chat_id, TEXTS[lang]['alarm_menu'], get_alarm_keyboard(lang), parse_mode='Markdown')
            user_states[chat_id] = {'step': 500, 'type': 'alarms'}
        
        # إضافة أمر إيقاف المنبه
        elif text == '/stop_alarm' or text == '🔕 Stop alarm' or text == '🔕 إيقاف المنبه':
            if chat_id in active_alarms:
                active_alarms[chat_id]['stop_requested'] = True
                send_message(chat_id, TEXTS[lang]['alarm_stopped'], get_main_keyboard(lang))
                del active_alarms[chat_id]
            else:
                send_message(chat_id, TEXTS[lang]['no_active_alarm'], get_main_keyboard(lang))
        
        elif text.lower() in ['cancel', 'إلغاء']:
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
        elif state.get('type') == 'settings':
            handle_settings(chat_id, text, lang)
        else:
            # إذا كان النص رقماً، معالجته كوقت
            if re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', text):
                handle_alarm_time(chat_id, text, lang)
            else:
                send_message(chat_id, TEXTS[lang]['invalid_time'], get_main_keyboard(lang))
    
    except ValueError:
        send_message(chat_id, TEXTS[lang]['invalid_number'], get_main_keyboard(lang))

# -------------------- Gestion des alarmes --------------------

def handle_alarms(chat_id, text, lang):
    state = user_states[chat_id]
    
    if text == '➕ New alarm' or text == '➕ منبه جديد':
        send_message(chat_id, TEXTS[lang]['new_alarm_name'], get_cancel_keyboard(lang))
        state['step'] = 501  # انتظار اسم المنبه
    
    elif text == '🗑️ Delete alarm' or text == '🗑️ حذف المنبه':
        if chat_id not in user_alarms or not user_alarms[chat_id]:
            send_message(chat_id, TEXTS[lang]['no_alarms'], get_alarm_keyboard(lang))
        else:
            alarm_list = "\n".join([f"{i+1}. {name} - {data['time']}" for i, (name, data) in enumerate(user_alarms[chat_id].items())])
            send_message(chat_id, TEXTS[lang]['select_alarm_to_delete'] + "\n" + alarm_list, get_cancel_keyboard(lang))
            state['step'] = 503  # انتظار اختيار المنبه للحذف
    
    elif text == '📋 List alarms' or text == '📋 قائمة المنبهات':
        if chat_id not in user_alarms or not user_alarms[chat_id]:
            send_message(chat_id, TEXTS[lang]['no_alarms'], get_alarm_keyboard(lang))
        else:
            alarm_list = ""
            for name, data in user_alarms[chat_id].items():
                alarm_list += TEXTS[lang]['alarm_item'].format(name, data['time'])
            send_message(chat_id, TEXTS[lang]['alarm_list'].format(alarm_list), get_alarm_keyboard(lang))
    
    elif state['step'] == 501:  # انتظار اسم المنبه
        state['new_alarm_name'] = text
        send_message(chat_id, TEXTS[lang]['new_alarm_time'], get_time_selection_keyboard(lang))
        state['step'] = 502  # انتظار وقت المنبه
    
    elif state['step'] == 502:  # انتظار وقت المنبه
        handle_alarm_time(chat_id, text, lang)
    
    elif state['step'] == 503:  # انتظار اختيار المنبه للحذف
        try:
            alarm_index = int(text) - 1
            alarm_name = list(user_alarms[chat_id].keys())[alarm_index]
            del user_alarms[chat_id][alarm_name]
            send_message(chat_id, TEXTS[lang]['alarm_deleted'].format(alarm_name), get_alarm_keyboard(lang))
            state['step'] = 500  # العودة إلى قائمة المنبهات
        except (ValueError, IndexError):
            send_message(chat_id, TEXTS[lang]['invalid_number'], get_alarm_keyboard(lang))

def handle_alarm_time(chat_id, text, lang):
    state = user_states[chat_id]
    
    # التحقق من صيغة الوقت
    if re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', text):
        if chat_id not in user_alarms:
            user_alarms[chat_id] = {}
        
        user_alarms[chat_id][state['new_alarm_name']] = {
            'time': text,
            'created': datetime.now().isoformat()
        }
        
        send_message(chat_id, TEXTS[lang]['alarm_added'].format(state['new_alarm_name'], text), get_alarm_keyboard(lang))
        state['step'] = 500  # العودة إلى قائمة المنبهات
    else:
        send_message(chat_id, TEXTS[lang]['invalid_time'], get_time_selection_keyboard(lang))

# -------------------- Gestion des paramètres --------------------

def handle_settings(chat_id, text, lang):
    state = user_states[chat_id]
    
    if text == '🗑️ Clear all alarms' or text == '🗑️ مسح جميع المنبهات':
        if 'confirm_clear' not in state:
            send_message(chat_id, TEXTS[lang]['confirm_clear_all'], get_cancel_keyboard(lang))
            state['confirm_clear'] = True
        else:
            if text.upper() in ['YES', 'نعم']:
                user_alarms[chat_id] = {}
                send_message(chat_id, TEXTS[lang]['all_alarms_cleared'], get_settings_keyboard(lang))
                state['confirm_clear'] = False
            else:
                send_message(chat_id, TEXTS[lang]['cancel'], get_settings_keyboard(lang))
                state['confirm_clear'] = False

# -------------------- Messages --------------------

def send_welcome_start(chat_id, lang='en'):
    send_message(chat_id, TEXTS[lang]['welcome'], get_main_keyboard(lang))

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
        response = requests.post(url, json=data, timeout=10)
        if response.status_code != 200:
            print(f"Error sending message: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {e}")

def set_webhook():
    """تعيين الويب هوك للبوت"""
    webhook_url = os.environ.get('WEBHOOK_URL', '') + '/webhook'
    if webhook_url:
        url = f"{TELEGRAM_API_URL}/setWebhook?url={webhook_url}"
        try:
            response = requests.get(url)
            print(f"Webhook set: {response.json()}")
        except requests.exceptions.RequestException as e:
            print(f"Error setting webhook: {e}")
    else:
        print("WEBHOOK_URL not set, using polling mode")

if __name__ == '__main__':
    # تعيين الويب هوك عند التشغيل
    set_webhook()
    
    # تشغيل التطبيق
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
