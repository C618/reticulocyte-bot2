def handle_video_download(chat_id, url):
    try:
        send_message(chat_id, "⏳ جاري معالجة طلبك...")
        
        # بدلاً من التحميل المباشر، نرسل روابط بديلة
        with youtube_dl.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'الفيديو')
            video_url = info.get('url', '')
            
        message = f"📹 {video_title}\n\n"
        message += "للأسف، لا يمكنني تحميل الفيديو مباشرة على هذا الخادم.\n"
        message += f"رابط التحميل المباشر: {video_url}\n\n"
        message += "يمكنك استخدام هذا الرابط لتحميل الفيديو عبر أدوات أخرى."
        
        send_message(chat_id, message)
            
    except Exception as e:
        error_message = f"❌ حدث خطأ: {str(e)}"
        send_message(chat_id, error_message)
