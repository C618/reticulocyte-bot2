from flask import Flask, request, jsonify
import requests
import os
import re
import yt_dlp as youtube_dl
import tempfile
import json

app = Flask(__name__)

# توكن البوت الخاص بك
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# حالة المستخدمين
user_states = {}

# تكوين yt-dlp
ydl_opts = {
    'format': 'best[height<=720]',  أفضل جودة حتى 720p
    'outtmpl': '%(title)s.%(ext)s',
    'quiet': True,
}

@app.route('/')
def home():
    return "بوت حساب نسبة الريتيكولوسيت وتحميل الفيديوهات يعمل بشكل صحيح!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        
        if text == '/start':
            send_welcome_message(chat_id)
        elif text == '/calc':
            start_calculation(chat_id)
        elif text == '/download':
            send_download_instructions(chat_id)
        elif is_video_url(text):
            handle_video_download(chat_id, text)
        elif chat_id in user_states and user_states[chat_id].get('mode') == 'calculation':
            handle_calculation_input(chat_id, text)
        else:
            send_message(chat_id, "⚠️ لم أفهم طلبك. اكتب /start لرؤية الأوامر المتاحة.")
    
    return jsonify({'status': 'ok'})

def send_welcome_message(chat_id):
    message = "مرحباً! أنا بوت متعدد الوظائف.\n\n"
    message += "✅ يمكنني مساعدتك في:\n"
    message += "1. حساب نسبة الريتيكولوسيت (اكتب /calc)\n"
    message += "2. تحميل الفيديوهات من YouTube, Instagram, TikTok (اكتب /download)\n\n"
    message += "اختر الخدمة التي تريدها!"
    send_message(chat_id, message)

def start_calculation(chat_id):
    send_message(chat_id, "لنبدأ عملية الحساب. أدخل عدد الريتيكولوسيت في كل champ (المجموع 10).")
    send_message(chat_id, "أدخل عدد الريتيكولوسيت في Champ 1:")
    user_states[chat_id] = {'mode': 'calculation', 'step': 1, 'reti_counts': [], 'rbc_counts': []}

def send_download_instructions(chat_id):
    message = "📥 لتحميل فيديو،只需 أرسل لي الرابط من:\n\n"
    message += "• YouTube\n• Instagram\n• TikTok\n\n"
    message += "سأقوم بتحميل الفيديو وإرساله لك مباشرة!"
    send_message(chat_id, message)

def is_video_url(text):
    # patterns for YouTube, Instagram, and TikTok URLs
    youtube_pattern = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+'
    instagram_pattern = r'(https?://)?(www\.)?instagram\.com/.+'
    tiktok_pattern = r'(https?://)?(www\.)?tiktok\.com/.+'
    
    return (re.match(youtube_pattern, text) or 
            re.match(instagram_pattern, text) or 
            re.match(tiktok_pattern, text))

def handle_video_download(chat_id, url):
    try:
        send_message(chat_id, "⏳ جاري تحميل الفيديو، يرجى الانتظار...")
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts['outtmpl'] = os.path.join(tmp_dir, '%(title)s.%(ext)s')
            
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # إرسال الفيديو إلى المستخدم
                with open(filename, 'rb') as video_file:
                    files = {'video': video_file}
                    data = {'chat_id': chat_id}
                    requests.post(f"{TELEGRAM_API_URL}/sendVideo", data=data, files=files)
                
                send_message(chat_id, "✅ تم تحميل الفيديو بنجاح!")
                
    except Exception as e:
        error_message = f"❌ حدث خطأ أثناء التحميل: {str(e)}"
        send_message(chat_id, error_message)

def handle_calculation_input(chat_id, text):
    state = user_states[chat_id]
    
    try:
        value = int(text)
        if value < 0:
            send_message(chat_id, "⚠️ الرجاء إدخال رقم موجب فقط.")
            return
    except ValueError:
        send_message(chat_id, "⚠️ الرجاء إدخال رقم صحيح.")
        return
    
    if state['step'] <= 10:
        # جمع قيم الريتيكولوسيت
        state['reti_counts'].append(value)
        
        if state['step'] < 10:
            send_message(chat_id, f"أدخل عدد الريتيكولوسيت في Champ {state['step'] + 1}:")
            state['step'] += 1
        else:
            send_message(chat_id, "تم جمع جميع قيم الريتيكولوسيت. الآن أدخل عدد الكريات الحمراء في ربع Champ 1:")
            state['step'] = 11
    elif state['step'] <= 13:
        # جمع قيم الكريات الحمراء
        state['rbc_counts'].append(value)
        
        if state['step'] < 13:
            send_message(chat_id, f"أدخل عدد الكريات الحمراء في ربع Champ {state['step'] - 10}:")
            state['step'] += 1
        else:
            # حساب النتيجة
            reti_total = sum(state['reti_counts'])
            
            rbc1 = state['rbc_counts'][0] * 4
            rbc2 = state['rbc_counts'][1] * 4
            rbc3 = state['rbc_counts'][2] * 4
            
            avg_rbc = (rbc1 + rbc2 + rbc3) / 3
            rbc_total = avg_rbc * 10
            
            result = (reti_total / rbc_total) * 100
            
            # إرسال النتيجة
            message = f"--- النتيجة ---\n"
            message += f"مجموع الريتيكولوسيت = {reti_total}\n"
            message += f"متوسط الكريات الحمراء (×10) = {rbc_total:.2f}\n"
            message += f"نسبة الريتيكولوسيت = {result:.2f} %"
            
            send_message(chat_id, message)
            
            # إعادة تعيين الحالة
            user_states[chat_id] = {'mode': 'calculation', 'step': 0, 'reti_counts': [], 'rbc_counts': []}

def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, json=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
