import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
import psutil

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from config import Config
from utils.subtitle_processor import SubtitleProcessor
from utils.file_handler import FileHandler
from utils.progress_manager import ProgressManager

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SubtitleBot:
    def __init__(self):
        self.config = Config()
        self.config.setup_directories()
        self.processor = SubtitleProcessor(self.config)
        self.file_handler = FileHandler(self.config)
        self.user_data = {}
        
        self.system_info = {
            'total_memory': psutil.virtual_memory().total / 1024 / 1024 / 1024,
            'available_memory': psutil.virtual_memory().available / 1024 / 1024 / 1024,
            'cpu_count': psutil.cpu_count()
        }
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.file_handler.start()
        welcome_message = (
            f"👋 **Hello {user.first_name}!**\n\n"
            "🎬 **Welcome to the Subtitle Burner Bot!**\n\n"
            "I can permanently burn subtitles into your videos with ultra-fast processing.\n\n"
            "**📤 How to use:**\n"
            "1️⃣ Send me a **video file** (MP4, MKV, AVI, etc. - up to 2GB)\n"
            "2️⃣ Then send me a **subtitle file** (.srt, .ass, .ssa, .vtt)\n"
            "3️⃣ I'll burn the subtitles and send you the processed video\n\n"
            "⚡ **Features:**\n"
            "• 🚀 Ultra-fast processing with FFmpeg\n"
            "• 📊 Real-time progress updates\n"
            "• 🌍 Supports all languages (Unicode)\n"
            "• 💾 Permanent hard-burned subtitles\n"
            "• 📦 Supports files up to 2GB\n\n"
            f"📊 **System:** {self.system_info['cpu_count']} cores, {self.system_info['available_memory']:.1f}GB RAM\n\n"
            "Send a video to get started! 🚀"
        )
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "📖 **How to use**\n\n"
            "1️⃣ Send a **video file** (mp4, mkv, avi, etc.)\n"
            "2️⃣ Send a **subtitle file** (.srt, .ass, .ssa, .vtt)\n"
            "3️⃣ Receive your video with hard-burned subtitles!\n\n"
            "**Commands:**\n"
            "/start - Start\n/help - Help\n/status - Bot status\n/cancel - Cancel"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        active_jobs = self.processor.get_all_jobs()
        status_text = (
            f"📊 **Bot Status**\n\n✅ Running\n"
            f"⚡ Preset: `{self.config.ENCODING_PRESET}`\n"
            f"🔢 Threads: {self.config.FFMPEG_THREADS}\n"
            f"🎬 Active jobs: {len(active_jobs)}\n"
            f"💾 Memory: {self.system_info['available_memory']:.1f}GB / {self.system_info['total_memory']:.1f}GB"
        )
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.user_data:
            self.user_data[user_id] = {}
            await update.message.reply_text("🔄 Cancelled.")
        else:
            await update.message.reply_text("ℹ️ No active operation.")
    
    async def handle_video_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles both video messages and document messages that are actually videos."""
        user_id = update.effective_user.id
        user_data = self.user_data.get(user_id, {})
        
        video = None
        file_name = None
        file_size = 0
        file_id = None
        detected = False
        
        # 1. Check if it's a video message
        if update.message.video:
            video = update.message.video
            file_name = video.file_name or f"video_{user_id}.mp4"
            file_size = video.file_size
            file_id = video.file_id
            detected = True
            logger.info(f"📹 Video message detected: {file_name}")
        
        # 2. Check if it's a document
        elif update.message.document:
            doc = update.message.document
            doc_name = doc.file_name or ""
            doc_ext = Path(doc_name).suffix.lower()
            mime = doc.mime_type or ""
            
            logger.info(f"📄 Document received: name='{doc_name}', ext='{doc_ext}', mime='{mime}'")
            
            # Check if it's a video by mime_type or extension
            is_video_mime = mime.startswith('video/')
            is_video_ext = doc_ext in self.config.SUPPORTED_VIDEO_FORMATS
            
            if is_video_mime or is_video_ext:
                video = doc
                file_name = doc_name if doc_name else f"video_{user_id}{doc_ext or '.mp4'}"
                file_size = doc.file_size
                file_id = doc.file_id
                detected = True
                logger.info(f"🎬 Document recognized as video: {file_name}")
            else:
                # Not a video, maybe subtitle
                if doc_ext in self.config.SUPPORTED_SUB_FORMATS:
                    return await self.handle_subtitle_input(update, context)
                else:
                    await update.message.reply_text(
                        f"❌ **Unsupported file format!**\n\n"
                        f"File: `{doc_name}`\n"
                        f"Extension: `{doc_ext}`\n\n"
                        f"Send a video (MP4, MKV, AVI, etc.) or subtitle (.srt, .ass, .vtt)."
                    )
                    return
        
        if not detected:
            await update.message.reply_text(
                "❌ **Please send a video file!**\n\n"
                "Send a video file (MP4, MKV, AVI, etc.) first.\n"
                "Then send the subtitle file."
            )
            return
        
        # Check file size
        if file_size > self.config.MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ **File too large!** ({file_size/1024/1024/1024:.2f}GB)\nMax: 2GB"
            )
            return
        
        # Store video info
        user_data['video_file'] = video
        user_data['video_file_id'] = file_id
        user_data['video_name'] = file_name
        user_data['video_size'] = file_size
        self.user_data[user_id] = user_data
        
        await update.message.reply_text(
            f"✅ **Video received!**\n\n"
            f"📹 File: `{file_name}`\n"
            f"📦 Size: {file_size/1024/1024:.1f}MB\n\n"
            "📝 Now send me the **subtitle file**\n"
            "(.srt, .ass, .ssa, .vtt)\n\n"
            "⚠️ Send it as a **document** (file attachment)."
        )
    
    async def handle_subtitle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Check if video was stored
        if user_id not in self.user_data or 'video_file' not in self.user_data[user_id]:
            await update.message.reply_text(
                "❌ **Please send a video first!**\n\n"
                "1️⃣ Send a video file (MP4, MKV, AVI, etc.)\n"
                "2️⃣ Then send the subtitle file"
            )
            return
        
        doc = update.message.document
        if not doc:
            await update.message.reply_text("❌ Please send a subtitle file as a document.")
            return
        
        file_name = doc.file_name or ""
        file_ext = Path(file_name).suffix.lower()
        
        # Check if it's a video document (in case user sends video again)
        if file_ext in self.config.SUPPORTED_VIDEO_FORMATS or (doc.mime_type and doc.mime_type.startswith('video/')):
            return await self.handle_video_input(update, context)
        
        # Check subtitle format
        if file_ext not in self.config.SUPPORTED_SUB_FORMATS:
            await update.message.reply_text(
                f"❌ **Unsupported subtitle format!**\n\n"
                f"File: `{file_name}`\n"
                f"Extension: `{file_ext}`\n\n"
                f"Supported: {', '.join(self.config.SUPPORTED_SUB_FORMATS)}"
            )
            return
        
        if doc.file_size > self.config.MAX_SUBTITLE_SIZE:
            await update.message.reply_text(
                f"❌ **Subtitle too large!** ({doc.file_size/1024/1024:.1f}MB)\nMax: 50MB"
            )
            return
        
        # Proceed with processing
        user_data = self.user_data[user_id]
        video_file_id = user_data['video_file_id']
        video_name = user_data['video_name']
        
        progress_msg = await update.message.reply_text(
            "🔄 **Starting processing...**\n\n"
            "📥 Downloading files...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        job_dir = os.path.join(self.config.TEMP_DIR, f"job_{user_id}_{int(datetime.now().timestamp())}")
        os.makedirs(job_dir, exist_ok=True)
        
        try:
            await self.file_handler.start()
            
            # Determine video extension
            video_ext = Path(video_name).suffix.lower()
            if not video_ext or video_ext not in self.config.SUPPORTED_VIDEO_FORMATS:
                video_ext = '.mp4'
            video_path = os.path.join(job_dir, f"video_{user_id}{video_ext}")
            subtitle_path = os.path.join(job_dir, file_name)
            
            # Download video
            async def dl_progress(curr, total):
                pct = int((curr/total)*100)
                if pct % 10 == 0:
                    try:
                        await progress_msg.edit_text(
                            f"📥 **Downloading video...**\n\n"
                            f"📊 {pct}%\n"
                            f"📦 {curr/1024/1024:.1f}MB / {total/1024/1024:.1f}MB",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
            
            await progress_msg.edit_text(
                f"📥 **Downloading video...**\n"
                f"📦 {user_data['video_size']/1024/1024:.1f}MB",
                parse_mode=ParseMode.MARKDOWN
            )
            await self.file_handler.download_file(video_file_id, video_path, dl_progress)
            
            # Download subtitle
            await progress_msg.edit_text(
                f"📥 **Downloading subtitle...**\n"
                f"📦 {doc.file_size/1024:.1f}KB",
                parse_mode=ParseMode.MARKDOWN
            )
            await self.file_handler.download_file(doc.file_id, subtitle_path)
            
            # Process
            await progress_msg.edit_text(
                "🎬 **Burning subtitles...**\n\n"
                "⏳ This may take a few minutes.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            async def enc_progress(percentage, speed, stage):
                try:
                    await progress_msg.edit_text(
                        f"🔄 **{stage}**\n\n"
                        f"📊 {percentage}%\n"
                        f"⚡ {speed:.1f} MB/s",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            
            output_path, progress = await self.processor.process_video(
                video_path, subtitle_path,
                output_name=f"hardsub_{user_id}_{int(datetime.now().timestamp())}.mp4",
                job_id=f"job_{user_id}_{int(datetime.now().timestamp())}"
            )
            progress.callback = enc_progress
            
            while not progress.is_complete:
                await asyncio.sleep(0.5)
            
            await progress_msg.edit_text(
                "✅ **Processing complete!**\n\n📤 Uploading...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            output_size = os.path.getsize(output_path)
            
            async def up_progress(curr, total):
                pct = int((curr/total)*100)
                if pct % 10 == 0:
                    try:
                        await progress_msg.edit_text(
                            f"📤 **Uploading...**\n\n"
                            f"📊 {pct}%\n"
                            f"📦 {curr/1024/1024:.1f}MB / {total/1024/1024:.1f}MB",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
            
            await progress_msg.edit_text(
                f"📤 **Uploading video...**\n"
                f"📦 {output_size/1024/1024:.1f}MB",
                parse_mode=ParseMode.MARKDOWN
            )
            
            await self.file_handler.send_video_to_user(
                chat_id=user_id,
                video_path=output_path,
                caption=(
                    f"🎬 **Video with Hard-Burned Subtitles**\n\n"
                    f"✅ Subtitles permanently burned in!\n"
                    f"⚡ Ultra-fast processing\n"
                    f"📦 {output_size/1024/1024:.1f}MB\n"
                    f"⏱️ {progress.get_elapsed_time()}"
                ),
                progress_callback=up_progress
            )
            
            await self.processor.cleanup(job_dir)
            self.user_data.pop(user_id, None)
            
            await progress_msg.edit_text(
                f"✅ **Done!**\n\n⏱️ Total time: {progress.get_elapsed_time()}\n\nSend another video to continue!"
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Processing error: {error_msg}")
            
            # Get more details from the error
            if "FFmpeg encoding failed" in error_msg:
                # Try to get more details from the error
                error_parts = error_msg.split('\n')
                formatted_error = "\n".join(error_parts[:3])  # Show first 3 lines
                await progress_msg.edit_text(
                    f"❌ **FFmpeg Error:**\n\n"
                    f"`{formatted_error}`\n\n"
                    f"Possible issues:\n"
                    f"• Video file might be corrupted\n"
                    f"• Subtitle format might be incompatible\n"
                    f"• Try converting video to MP4 first\n\n"
                    f"Please try again with a different file.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await progress_msg.edit_text(
                    f"❌ **Error:**\n\n"
                    f"`{error_msg[:200]}`\n\n"
                    f"Please try again with a different file.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await self.processor.cleanup(job_dir)
            self.user_data.pop(user_id, None)

async def main():
    bot = SubtitleBot()
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("status", bot.status_command))
    app.add_handler(CommandHandler("cancel", bot.cancel_command))
    
    # Main handlers
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, bot.handle_video_input))
    
    print("🚀 Bot started!")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Shutting down...")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
