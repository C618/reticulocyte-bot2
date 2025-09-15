from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import re
import os
import logging
from datetime import datetime

# إعداد التطبيق
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# التوكن من متغيرات البيئة
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# المتغيرات العامة
user_states = {}
user_languages = {}
user_channels = {}
calculations_history = []

# -------------------- دوال المختبر الطبي --------------------

def get_main_keyboard(lang='fr'):
    """لوحة المفاتيح الرئيسية للمختبر الطبي"""
    keyboards = {
        'fr': {
            'keyboard': [
                ['🔢 Réticulocytes', '🩸 Plaquettes'],
                ['🧪 Dilution', '⚙️ Paramètres'],
                ['ℹ️ Aide', '🔄 Langue']
            ],
            'resize_keyboard': True
        },
        # ... باقي اللغات
    }
    return keyboards.get(lang, keyboards['fr'])

# -------------------- دوال قنوات M3U --------------------

def parse_m3u_content(content):
    """تحليل محتوى ملف M3U"""
    channels = []
    lines = content.split('\n')
    channel = {}
    
    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF:'):
            match = re.search(r'#EXTINF:-1.*?,(.+)', line)
            if match:
                channel = {'name': match.group(1).strip(), 'url': ''}
        elif line and not line.startswith('#'):
            if channel and 'name' in channel:
                channel['url'] = line
                channels.append(channel)
                channel = {}
    
    return channels

def create_channels_keyboard(channels, page=0):
    """إنشاء لوحة مفاتيح للقنوات"""
    keyboard = InlineKeyboardMarkup()
    items_per_page = 8
    start_idx = page * items_per_page
    
    for i in range(start_idx, min(start_idx + items_per_page, len(channels))):
        name = channels[i]['name'][:30] + "..." if len(channels[i]['name']) > 30 else channels[i]['name']
        keyboard.add(InlineKeyboardButton(f"📺 {name}", callback_data=f"m3u_play_{i}"))
    
    # أزرار التنقل
    if page > 0:
        keyboard.add(InlineKeyboardButton("⬅️ السابق", callback_data=f"m3u_page_{page-1}"))
    if start_idx + items_per_page < len(channels):
        keyboard.add(InlineKeyboardButton("التالي ➡️", callback_data=f"m3u_page_{page+1}"))
    
    return keyboard

# -------------------- معالجة أوامر المختبر الطبي --------------------

@bot.message_handler(commands=['start', 'help', 'calc', 'plaquettes', 'dilution'])
def handle_commands(message):
    """معالجة الأوامر الأساسية"""
    chat_id = message.chat.id
    lang = user_languages.get(chat_id, 'fr')
    
    if message.text == '/start':
        send_welcome_start(chat_id, lang)
    elif message.text == '/help':
        bot.send_message(chat_id, TEXTS[lang]['help_text'], reply_markup=get_main_keyboard(lang))
    # ... باقي الأوامر

# -------------------- معالجة قنوات M3U --------------------

@bot.message_handler(commands=['load'])
def handle_load_m3u(message):
    """تحميل قنوات M3U من رابط"""
    try:
        parts = message.text.split(' ', 1)
        if len(parts) < 2:
            bot.reply_to(message, "📝 usage: /load <m3u_url>")
            return
            
        url = parts[1]
        response = requests.get(url)
        
        if response.status_code != 200:
            bot.reply_to(message, "❌无法从该URL获取内容")
            return
            
        channels = parse_m3u_content(response.text)
        
        if not channels:
            bot.reply_to(message, "❌未在链接中找到频道")
            return
            
        user_channels[message.chat.id] = channels
        keyboard = create_channels_keyboard(channels, 0)
        
        bot.reply_to(message, f"✅成功加载 {len(channels)} 个频道!", reply_markup=keyboard)
        
    except Exception as e:
        bot.reply_to(message, f"❌错误: {str(e)}")

@bot.message_handler(content_types=['document'])
def handle_m3u_file(message):
    """معالجة ملف M3U"""
    try:
        file_info = bot.get_file(message.document.file_id)
        
        if not message.document.file_name.endswith('.m3u'):
            bot.reply_to(message, "❌ يرجى إرسال ملف M3U صحيح")
            return
            
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8')
        channels = parse_m3u_content(content)
        
        if not channels:
            bot.reply_to(message, "❌ لم يتم العثور على قنوات في الملف")
            return
            
        user_channels[message.chat.id] = channels
        keyboard = create_channels_keyboard(channels, 0)
        
        bot.reply_to(message, f"✅ تم تحميل {len(channels)} قناة!", reply_markup=keyboard)
        
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ: {str(e)}")

# -------------------- معالجة الأزرار التفاعلية --------------------

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """معالجة الضغط على الأزرار"""
    try:
        if call.data.startswith('m3u_'):
            # معالجة أزرار M3U
            if call.data.startswith('m3u_play_'):
                channel_idx = int(call.data.split('_')[2])
                if call.message.chat.id in user_channels:
                    channel = user_channels[call.message.chat.id][channel_idx]
                    bot.send_message(call.message.chat.id, 
                                   f"📺 **{channel['name']}**\n\n🔗 {channel['url']}",
                                   parse_mode='Markdown')
            
            elif call.data.startswith('m3u_page_'):
                page = int(call.data.split('_')[2])
                if call.message.chat.id in user_channels:
                    keyboard = create_channels_keyboard(user_channels[call.message.chat.id], page)
                    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, 
                                                reply_markup=keyboard)
        
        elif call.data.startswith('lab_'):
            # معالجة أزرار المختبر الطبي
            pass
            
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ حدث خطأ: {str(e)}")

# -------------------- دعم ويب هوك Flask --------------------

@app.route('/')
def home():
    return "Bot is running! ✅"

@app.route('/webhook', methods=['POST'])
def webhook():
    """ويب هوك لاستقبال التحديثات"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'})

# -------------------- التشغيل الرئيسي --------------------

def set_webhook():
    """تعيين الويب هوك"""
    webhook_url = os.environ.get('WEBHOOK_URL') + '/webhook'
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"Webhook set to: {webhook_url}")

if __name__ == '__main__':
    set_webhook()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
