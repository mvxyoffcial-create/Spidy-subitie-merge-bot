import os
import asyncio
import time
import logging
from datetime import datetime
from pathlib import Path
from aiohttp import web

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import MessageMediaType

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

# Initialize
config = Config()
config.setup_directories()
processor = SubtitleProcessor(config)
file_handler = FileHandler(config)

user_data = {}
progress_messages = {}

# --- Web Server for Health Checks ---
async def health_check(request):
    return web.Response(text="OK", status=200)

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", health_check)
    server.router.add_get("/health", health_check)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logger.info(f"✅ Web server on port {config.PORT}")

# --- Progress Callback ---
async def progress_callback(current, total, message, operation):
    """Update progress message"""
    try:
        percentage = (current / total * 100) if total > 0 else 0
        speed = current / (1024 * 1024) / max(1, time.time() - start_time) if 'start_time' in locals() else 0
        
        bar = '█' * int(percentage / 5) + '░' * (20 - int(percentage / 5))
        
        status_text = (
            f"📊 **{operation}**\n\n"
            f"`{bar}` **{percentage:.1f}%**\n\n"
            f"📦 **Size:** {current / 1024 / 1024:.1f}MB / {total / 1024 / 1024:.1f}MB\n"
        )
        
        await message.edit_text(status_text)
    except Exception as e:
        logger.error(f"Progress update error: {e}")

# --- Bot Commands ---
@Client.on_message(filters.command(["start", "help"]))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 **Fast Hardsub Bot**\n\n"
        "1️⃣ Send me a **Video File** (up to 2GB)\n"
        "2️⃣ Send me a **Subtitle File** (.srt, .ass, .vtt)\n"
        "3️⃣ I'll burn subtitles and send back!\n\n"
        "⚡ **Ultra-fast** with FFmpeg\n"
        "📊 **Real-time progress**\n"
        "🌍 **All languages supported**"
    )

@Client.on_message(filters.video | filters.document)
async def handle_media(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check if it's a subtitle file
    doc = message.document or message.video
    if not doc:
        return
    
    file_name = doc.file_name or "file.mp4"
    file_ext = Path(file_name).suffix.lower()
    
    # If subtitle
    if file_ext in config.SUPPORTED_SUB_FORMATS:
        if user_id not in user_data or 'video_path' not in user_data[user_id]:
            await message.reply_text("❌ Please send the video file first!")
            return
        
        status_msg = await message.reply_text("📥 Downloading subtitle...")
        
        # Download subtitle
        sub_path = os.path.join(config.TEMP_DIR, f"sub_{user_id}{file_ext}")
        await message.download(file_name=sub_path)
        
        user_data[user_id]['sub_path'] = sub_path
        
        await status_msg.edit_text(
            "✅ **Subtitle Received!**\n\n"
            "🔄 Starting hardsub process...\n"
            "⏳ This may take a few minutes."
        )
        
        # Process video
        await process_hardsub(client, message, user_id, status_msg)
    
    # If video
    else:
        status_msg = await message.reply_text("📥 Downloading video...")
        
        # Download video
        video_path = os.path.join(config.TEMP_DIR, f"vid_{user_id}.mp4")
        await message.download(file_name=video_path)
        
        user_data[user_id] = {
            'video_path': video_path,
            'video_size': doc.file_size
        }
        
        await status_msg.edit_text(
            "✅ **Video Downloaded!**\n\n"
            "📝 Now send the **subtitle file**\n"
            f"Supported: {', '.join(config.SUPPORTED_SUB_FORMATS)}"
        )

async def process_hardsub(client: Client, message: Message, user_id: int, status_msg: Message):
    """Process hardsub with progress"""
    try:
        video_path = user_data[user_id]['video_path']
        sub_path = user_data[user_id]['sub_path']
        
        # Output path
        output_path = os.path.join(config.OUTPUT_DIR, f"output_{user_id}.mp4")
        
        # Update status
        await status_msg.edit_text("🔥 **Burning subtitles...**\n\n⏳ Processing...")
        
        # Process with progress
        progress = await processor.burn_subtitles(video_path, sub_path, output_path, "x264")
        
        # Create progress updater
        async def update_progress():
            last_text = ""
            while not progress.is_complete:
                await asyncio.sleep(2)
                status_text = progress.get_status_text()
                if status_text != last_text:
                    try:
                        await status_msg.edit_text(status_text)
                        last_text = status_text
                    except:
                        pass
        
        # Start progress updates
        await asyncio.gather(update_progress())
        
        # Upload result
        await status_msg.edit_text("📤 **Uploading hardsubbed video...**")
        
        # Send video
        await client.send_video(
            chat_id=user_id,
            video=output_path,
            caption=f"✅ **Hardsub Complete!**\n\n⏱️ Time: {progress.get_elapsed_time()}\n📦 Size: {progress.format_size(os.path.getsize(output_path))}",
            supports_streaming=True
        )
        
        await status_msg.edit_text("✅ **Done!** Video with hard-burned subtitles sent!")
        
        # Cleanup
        for path in [video_path, sub_path, output_path]:
            if os.path.exists(path):
                os.remove(path)
        
        if user_id in user_data:
            del user_data[user_id]
            
    except Exception as e:
        logger.error(f"Processing error: {e}")
        await status_msg.edit_text(f"❌ **Error:** {str(e)[:200]}\n\nPlease try again.")

# --- Run Bot ---
async def main():
    # Create app
    app = Client(
        "hardsub_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN
    )
    
    # Register handlers
    app.on_message(filters.command(["start", "help"]))(start_command)
    app.on_message(filters.video | filters.document)(handle_media)
    
    # Start web server
    await start_web_server()
    
    # Start bot
    logger.info("🚀 Starting bot...")
    await app.start()
    logger.info("✅ Bot is running!")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
