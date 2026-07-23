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
        self.user_data = {}  # Store user data in memory
        
        # System monitoring
        self.system_info = {
            'total_memory': psutil.virtual_memory().total / 1024 / 1024 / 1024,
            'available_memory': psutil.virtual_memory().available / 1024 / 1024 / 1024,
            'cpu_count': psutil.cpu_count()
        }
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when /start is issued."""
        user = update.effective_user
        
        # Initialize file handler
        await self.file_handler.start()
        
        welcome_message = (
            f"👋 **Hello {user.first_name}!**\n\n"
            "🎬 **Welcome to the Subtitle Burner Bot!**\n\n"
            "I can permanently burn subtitles into your videos with ultra-fast processing.\n\n"
            "**📤 How to use:**\n"
            "1️⃣ Send me a **video file** (up to 2GB)\n"
            "2️⃣ Then send me a **subtitle file** (.srt, .ass, .ssa, .vtt)\n"
            "3️⃣ I'll burn the subtitles and send you the processed video\n\n"
            "⚡ **Features:**\n"
            "• 🚀 Ultra-fast processing with FFmpeg\n"
            "• 📊 Real-time progress updates\n"
            "• 🌍 Supports all languages (Unicode)\n"
            "• 💾 Permanent hard-burned subtitles\n"
            "• 📦 Supports files up to 2GB\n"
            "• 🎯 Multiple subtitle formats supported\n\n"
            "📊 **System Status:**\n"
            f"• 💻 CPU Cores: {self.system_info['cpu_count']}\n"
            f"• 🧠 RAM Available: {self.system_info['available_memory']:.1f}GB\n\n"
            "Send a video to get started! 🚀"
        )
        
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send help message."""
        help_text = (
            "📖 **How to use the Subtitle Bot**\n\n"
            "**Step-by-Step:**\n"
            "1️⃣ Send a **video file** (mp4, avi, mkv, mov, etc.)\n"
            "2️⃣ Send a **subtitle file** (.srt, .ass, .ssa, .vtt)\n"
            "3️⃣ Wait for processing (progress shown in real-time)\n"
            "4️⃣ Receive your video with hard-burned subtitles!\n\n"
            "**⚡ Features:**\n"
            "• Ultra-fast processing with FFmpeg\n"
            "• Real-time progress updates\n"
            "• Supports all languages (Unicode)\n"
            "• Maximum file size: 2GB\n"
            "• Permanent hard-burned subtitles\n"
            "• Multi-threaded for maximum speed\n\n"
            "**🔧 Commands:**\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/status - Check bot status\n"
            "/cancel - Cancel current operation\n\n"
            "**📝 Supported formats:**\n"
            "• Videos: MP4, AVI, MKV, MOV, FLV, WEBM\n"
            "• Subtitles: SRT, ASS, SSA, VTT, SUB"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check bot status."""
        active_jobs = self.processor.get_all_jobs()
        
        status_text = (
            "📊 **Bot Status**\n\n"
            "✅ **Bot is running**\n\n"
            f"⚡ **Encoding preset:** `{self.config.ENCODING_PRESET}`\n"
            f"🔢 **CPU Threads:** {self.config.FFMPEG_THREADS}\n"
            f"📦 **Max file size:** 2GB\n"
            f"🎬 **Active jobs:** {len(active_jobs)}\n\n"
            "**Supported formats:**\n"
            f"• Videos: {', '.join(self.config.SUPPORTED_VIDEO_FORMATS)}\n"
            f"• Subtitles: {', '.join(self.config.SUPPORTED_SUB_FORMATS)}\n\n"
            f"💾 **Memory available:** {self.system_info['available_memory']:.1f}GB / {self.system_info['total_memory']:.1f}GB"
        )
        
        if active_jobs:
            status_text += "\n\n**Active Jobs:**"
            for job_id, progress in active_jobs.items():
                status_text += f"\n• Job {job_id}: {progress.current_stage} ({progress.get_percentage()}%)"
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current operation."""
        user_id = update.effective_user.id
        
        if user_id in self.user_data:
            self.user_data[user_id] = {}
            await update.message.reply_text("🔄 Operation cancelled! You can start fresh.")
        else:
            await update.message.reply_text("ℹ️ No active operation to cancel.")
    
    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video file upload with progress."""
        user_id = update.effective_user.id
        user_data = self.user_data.get(user_id, {})
        
        # Check file size
        video = update.message.video
        
        if video.file_size > self.config.MAX_FILE_SIZE:
            file_size_gb = video.file_size / 1024 / 1024 / 1024
            await update.message.reply_text(
                f"❌ **File too large!**\n\n"
                f"📦 Your file: {file_size_gb:.2f}GB\n"
                f"🚫 Maximum allowed: 2GB\n\n"
                "Please send a smaller video file."
            )
            return
        
        # Check video duration
        if video.duration and video.duration > self.config.MAX_VIDEO_DURATION:
            minutes = video.duration // 60
            await update.message.reply_text(
                f"❌ **Video too long!**\n\n"
                f"⏱️ Your video: {minutes} minutes\n"
                f"🚫 Maximum allowed: 2 hours\n\n"
                "Please send a shorter video."
            )
            return
        
        # Store video info
        user_data['video_file'] = video
        user_data['video_file_id'] = video.file_id
        user_data['video_name'] = video.file_name or f"video_{user_id}_{int(datetime.now().timestamp())}.mp4"
        user_data['video_size'] = video.file_size
        
        self.user_data[user_id] = user_data
        
        # Send confirmation
        await update.message.reply_text(
            f"✅ **Video received!**\n\n"
            f"📹 File: `{user_data['video_name']}`\n"
            f"📦 Size: {video.file_size / 1024 / 1024:.1f}MB\n"
            f"⏱️ Duration: {video.duration // 60}:{video.duration % 60:02d}\n\n"
            "📝 Now send me the **subtitle file**\n"
            "Supported formats: .srt, .ass, .ssa, .vtt"
        )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document file upload (subtitles) with 2GB support."""
        user_id = update.effective_user.id
        
        # Check if video was uploaded
        if user_id not in self.user_data or 'video_file' not in self.user_data[user_id]:
            await update.message.reply_text(
                "❌ **Please send a video first!**\n\n"
                "1️⃣ Send a video file\n"
                "2️⃣ Then send the subtitle file\n\n"
                "This ensures I can process your file correctly."
            )
            return
        
        # Check document
        document = update.message.document
        if not document:
            await update.message.reply_text("❌ Please send a subtitle file.")
            return
        
        file_name = document.file_name or ''
        file_ext = Path(file_name).suffix.lower()
        
        # Check subtitle format
        if file_ext not in self.config.SUPPORTED_SUB_FORMATS:
            await update.message.reply_text(
                f"❌ **Unsupported subtitle format!**\n\n"
                f"📝 Your file: `{file_name}`\n"
                f"❌ Extension: `{file_ext}`\n\n"
                f"**Supported formats:**\n"
                f"• {', '.join(self.config.SUPPORTED_SUB_FORMATS)}\n\n"
                "Please send a supported subtitle file."
            )
            return
        
        # Check subtitle file size
        if document.file_size > self.config.MAX_SUBTITLE_SIZE:
            await update.message.reply_text(
                f"❌ **Subtitle file too large!**\n\n"
                f"📦 Size: {document.file_size / 1024 / 1024:.1f}MB\n"
                f"🚫 Maximum: 50MB\n\n"
                "Please send a smaller subtitle file."
            )
            return
        
        # Get user data
        user_data = self.user_data[user_id]
        video_file = user_data['video_file']
        video_name = user_data['video_name']
        
        # Send processing message
        progress_message = await update.message.reply_text(
            "🔄 **Starting processing...**\n\n"
            "📥 Downloading files using Telegram API...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Create temporary directory for this job
        job_dir = os.path.join(self.config.TEMP_DIR, f"job_{user_id}_{int(datetime.now().timestamp())}")
        os.makedirs(job_dir, exist_ok=True)
        
        try:
            # Initialize file handler
            await self.file_handler.start()
            
            # Download video with progress
            video_path = os.path.join(job_dir, video_name)
            subtitle_path = os.path.join(job_dir, file_name)
            
            # Define progress callback for download
            async def download_progress(current, total):
                percentage = int((current / total) * 100)
                if percentage % 10 == 0:  # Update every 10%
                    await progress_message.edit_text(
                        f"📥 **Downloading video...**\n\n"
                        f"📊 Progress: {percentage}%\n"
                        f"📦 {current / 1024 / 1024:.1f}MB / {total / 1024 / 1024:.1f}MB",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            # Download video using Pyrogram (supports 2GB)
            await progress_message.edit_text(
                f"📥 **Downloading video file...**\n"
                f"📦 Size: {video_file.file_size / 1024 / 1024:.1f}MB\n\n"
                "⏳ Using Telegram API for large file support...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            await self.file_handler.download_file(
                video_file.file_id,
                video_path,
                download_progress
            )
            
            # Download subtitle
            await progress_message.edit_text(
                f"📥 **Downloading subtitle file...**\n"
                f"📦 Size: {document.file_size / 1024:.1f}KB",
                parse_mode=ParseMode.MARKDOWN
            )
            
            await self.file_handler.download_file(
                document.file_id,
                subtitle_path
            )
            
            # Process video with subtitles
            await progress_message.edit_text(
                "🎬 **Burning subtitles into video...**\n\n"
                "⏳ This may take a few minutes depending on file size.\n"
                "📊 Progress will update automatically...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Define progress callback for encoding
            async def encoding_progress(percentage, speed, stage):
                try:
                    status_text = (
                        f"🔄 **Processing: {stage}**\n\n"
                        f"📊 **Progress:** {percentage}%\n"
                        f"⚡ **Speed:** {speed:.1f} MB/s\n\n"
                        f"📦 **Processing:** {percentage}% complete"
                    )
                    await progress_message.edit_text(status_text, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.error(f"Error updating progress: {e}")
            
            # Start processing with progress tracking
            output_path, progress = await self.processor.process_video(
                video_path, 
                subtitle_path,
                output_name=f"hardsub_{user_id}_{int(datetime.now().timestamp())}.mp4",
                job_id=f"job_{user_id}_{int(datetime.now().timestamp())}"
            )
            
            # Set progress callback
            progress.callback = encoding_progress
            
            # Wait for processing to complete
            while not progress.is_complete:
                await asyncio.sleep(0.5)
            
            # Send final progress update
            await progress_message.edit_text(
                "✅ **Processing complete!**\n\n"
                "📤 Uploading your file using Telegram API...\n"
                "⏳ This may take a moment.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Upload the processed video
            output_size = os.path.getsize(output_path)
            
            # Define upload progress callback
            async def upload_progress(current, total):
                percentage = int((current / total) * 100)
                if percentage % 10 == 0:  # Update every 10%
                    await progress_message.edit_text(
                        f"📤 **Uploading video...**\n\n"
                        f"📊 Progress: {percentage}%\n"
                        f"📦 {current / 1024 / 1024:.1f}MB / {total / 1024 / 1024:.1f}MB",
                        parse_mode=ParseMode.MARKDOWN
                    )
            
            # Upload using Pyrogram for 2GB support
            await progress_message.edit_text(
                f"📤 **Uploading video...**\n"
                f"📦 Size: {output_size / 1024 / 1024:.1f}MB\n\n"
                "⏳ Using Telegram API for large file upload...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send video to user
            result = await self.file_handler.send_video_to_user(
                chat_id=user_id,
                video_path=output_path,
                caption=(
                    f"🎬 **Video with Hard-Burned Subtitles**\n\n"
                    f"✅ **Subtitles permanently burned in!**\n"
                    f"🌍 Supports all languages\n"
                    f"⚡ Processed with ultra-fast settings\n\n"
                    f"📦 **File size:** {output_size / 1024 / 1024:.1f}MB\n"
                    f"⏱️ **Processing time:** {progress.get_elapsed_time()}"
                ),
                progress_callback=upload_progress
            )
            
            # Clean up
            await self.processor.cleanup(job_dir)
            self.user_data.pop(user_id, None)
            
            await progress_message.edit_text(
                f"✅ **Done!** Your video with subtitles is ready.\n\n"
                f"⏱️ Total time: {progress.get_elapsed_time()}\n\n"
                "📤 Send another video to continue!"
            )
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            await progress_message.edit_text(
                f"❌ **Error processing video:**\n\n"
                f"`{str(e)}`\n\n"
                "Please try again with a different file.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Clean up on error
            await self.processor.cleanup(job_dir)
            self.user_data.pop(user_id, None)

async def main():
    """Start the bot."""
    # Create bot instance
    bot = SubtitleBot()
    
    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("status", bot.status_command))
    application.add_handler(CommandHandler("cancel", bot.cancel_command))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.VIDEO, bot.handle_video))
    application.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    
    # Start the bot
    print("🚀 Starting bot...")
    print(f"📝 Bot Token: {Config.BOT_TOKEN[:10]}...")
    print(f"📡 API ID: {Config.API_ID}")
    print(f"📦 Max File Size: 2GB")
    print("✅ Bot is running!")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Shutting down...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
