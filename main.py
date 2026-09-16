import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
import edge_tts

# লগিং সেটআপ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# বট টোকেন
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8952937185:AAF0qjCMokwh43ag7PE0er409ATwpOzOwf0")

# ==================== Render Web Service-এর জন্য ফেক হেলথ-চেক সার্ভার ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive and running on Render Web Service!")

    def log_message(self, format, *args):
        # সার্ভার লগ বন্ধ রাখার জন্য
        return

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"Fake Web Server running on port {port}")
    server.serve_forever()
# =========================================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """স্টার্ট কমান্ড হ্যান্ডলার"""
    await update.message.reply_text("হ্যালো! আমাকে একটি ভিডিও পাঠান। আমি সেটিকে ৩-৪ সেকেন্ডের ক্লিপে ভাগ করে প্রসেস ও ভয়েসওভার দিয়ে ফেরত পাঠাব।")

async def generate_voiceover(text: str, output_audio_path: str, voice: str = "bn-BD-NabanitaNeural"):
    """Edge-TTS ব্যবহার করে সম্পূর্ণ ফ্রিতে ভয়েস তৈরি করা"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_audio_path)

def process_video_pipeline(input_path: str, output_path: str, audio_path: str, clip_duration: int = 4):
    """ভিডিও কাটা, প্রসেস করা এবং অডিও জোড়া লাগানোর কাজ"""
    video = VideoFileClip(input_path)
    
    clips = []
    duration = int(video.duration)
    for i in range(0, duration, clip_duration):
        subclip = video.subclip(i, min(i + clip_duration, duration))
        clips.append(subclip)
    
    final_video = concatenate_videoclips(clips)
    
    if os.path.exists(audio_path):
        audio = AudioFileClip(audio_path)
        final_video = final_video.set_audio(audio)
        
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    video.close()
    final_video.close()

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ভিডিও রিসিভ করে প্রসেস করার ফাংশন"""
    msg = await update.message.reply_text("ভিডিওটি পাওয়া গেছে! প্রসেসিং শুরু হচ্ছে, কিছুটা সময় লাগতে পারে...")
    
    input_video_path = "temp_input.mp4"
    output_video_path = "temp_output.mp4"
    audio_path = "temp_voiceover.mp3"
    
    try:
        video_file = await update.message.video.get_file()
        await video_file.download_to_drive(input_video_path)
        
        script = "আপনার পাঠানো ভিডিওটি সফলভাবে প্রসেস করা হয়েছে।"
        await generate_voiceover(script, audio_path, voice="bn-BD-NabanitaNeural")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, process_video_pipeline, input_video_path, output_video_path, audio_path, 4)
        
        await update.message.reply_video(
            video=open(output_video_path, 'rb'),
            caption="আপনার প্রসেস করা ভিডিও রেডি!"
        )
        
    except Exception as e:
        await update.message.reply_text(f"একটি সমস্যা হয়েছে: {str(e)}")
        
    finally:
        for file_path in [input_video_path, output_video_path, audio_path]:
            if os.path.exists(file_path):
                os.remove(file_path)

if __name__ == '__main__':
    # ১. ব্যাকগ্রাউন্ড থ্রেডে ডামি ওয়েব সার্ভার চালু করা
    threading.Thread(target=run_web_server, daemon=True).start()

    # ২. টেলিগ্রাম বট স্টার্ট করা
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    print("Bot is running...")
    app.run_polling()
