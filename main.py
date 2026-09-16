import os
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
import edge_tts

# লগিং সেটআপ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# বট টোকেন (এনভায়রনমেন্ট ভেরিয়েবল থেকে নেওয়া ভালো)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """স্টার্ট কমান্ড হ্যান্ডলার"""
    await update.message.reply_text("হ্যালো! আমাকে একটি ভিডিও পাঠান। আমি সেটিকে ৩-৪ সেকেন্ডের ক্লিপে ভাগ করে প্রসেস ও ভয়েসওভার দিয়ে ফেরত পাঠাব।")

async def generate_voiceover(text: str, output_audio_path: str, voice: str = "bn-BD-NabanitaNeural"):
    """Edge-TTS ব্যবহার করে সম্পূর্ণ ফ্রিতে ভয়েস তৈরি করা"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_audio_path)

def process_video_pipeline(input_path: str, output_path: str, audio_path: str, clip_duration: int = 4):
    """ভিডিও কাটা, প্রসেস করা এবং অডিও জোড়া লাগানোর কাজ"""
    # ১. ভিডিও লোড করা
    video = VideoFileClip(input_path)
    
    # ২. ৩-৪ সেকেন্ডের ছোট টুকরোতে ভাগ করা
    clips = []
    duration = int(video.duration)
    for i in range(0, duration, clip_duration):
        subclip = video.subclip(i, min(i + clip_duration, duration))
        # [ভবিষ্যতে এআই মডেলের এডিটিং লজিক এই সাবক্লিপে যুক্ত করতে পারবেন]
        clips.append(subclip)
    
    # ৩. সব ক্লিপ আবার একসাথে জোড়া লাগানো
    final_video = concatenate_videoclips(clips)
    
    # ৪. তৈরি করা নতুন অডিও/ভয়েসওভার যুক্ত করা
    if os.path.exists(audio_path):
        audio = AudioFileClip(audio_path)
        # অডিও অনুযায়ী ভিডিওর সাউন্ড রিপ্লেস করা
        final_video = final_video.set_audio(audio)
        
    # ৫. ফাইনাল ভিডিও ফাইল আউটপুট দেওয়া
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    # মেমোরি ক্লিয়ার করা
    video.close()
    final_video.close()

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ভিডিও রিসিভ করে প্রসেস করার ফাংশন"""
    msg = await update.message.reply_text("ভিডিওটি পাওয়া গেছে! প্রসেসিং শুরু হচ্ছে, কিছুটা সময় লাগতে পারে...")
    
    input_video_path = "temp_input.mp4"
    output_video_path = "temp_output.mp4"
    audio_path = "temp_voiceover.mp3"
    
    try:
        # ১. টেলিগ্রাম থেকে ভিডিও ডাউনলোড
        video_file = await update.message.video.get_file()
        await video_file.download_to_drive(input_video_path)
        
        # ২. ভয়েসওভারের জন্য টেক্সট দিয়ে এআই ভয়েস বানানো
        script = "আপনার পাঠানো ভিডিওটি সফলভাবে প্রসেস করা হয়েছে।"
        await generate_voiceover(script, audio_path, voice="bn-BD-NabanitaNeural")
        
        # ৩. ব্যাকগ্রাউন্ডে ভিডিও কাটিং ও জোড়া লাগানোর ভারী কাজ চালানো
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, process_video_pipeline, input_video_path, output_video_path, audio_path, 4)
        
        # ৪. প্রসেস করা নতুন ভিডিও ইউজারের কাছে পাঠানো
        await update.message.reply_video(
            video=open(output_video_path, 'rb'),
            caption="আপনার প্রসেস করা ভিডিও রেডি!"
        )
        
    except Exception as e:
        await update.message.reply_text(f"একটি সমস্যা হয়েছে: {str(e)}")
        
    finally:
        # সাময়িক তৈরি হওয়া ফাইলগুলো মুছে ফেলা
        for file_path in [input_video_path, output_video_path, audio_path]:
            if os.path.exists(file_path):
                os.remove(file_path)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    print("Bot is running...")
    app.run_polling()
