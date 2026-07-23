import os
import asyncio
from pyrogram import Client
from pyrogram.errors import RPCError, FloodWait
import logging

logger = logging.getLogger(__name__)

class FileHandler:
    def __init__(self, config):
        self.config = config
        self.client = None
    
    def _init_client(self):
        if not self.client:
            self.client = Client(
                "hardsub_bot",
                api_id=self.config.API_ID,
                api_hash=self.config.API_HASH,
                bot_token=self.config.BOT_TOKEN,
                workdir=self.config.SESSIONS_DIR
            )
    
    async def start(self):
        if self.client and not self.client.is_connected:
            await self.client.start()
            logger.info("Client started")
    
    async def stop(self):
        if self.client and self.client.is_connected:
            await self.client.stop()
            logger.info("Client stopped")
    
    async def download_file(self, file_id: str, output_path: str, progress_callback=None):
        """Download file with progress"""
        await self.start()
        
        async def progress(current, total):
            if progress_callback:
                await progress_callback(current, total)
        
        try:
            await self.client.download_media(
                message=file_id,
                file_name=output_path,
                progress=progress
            )
            return output_path
        except FloodWait as e:
            await asyncio.sleep(e.value)
            return await self.download_file(file_id, output_path, progress_callback)
    
    async def send_video(self, chat_id: int, video_path: str, caption: str = "", progress_callback=None):
        """Send video with progress"""
        await self.start()
        
        async def progress(current, total):
            if progress_callback:
                await progress_callback(current, total)
        
        try:
            return await self.client.send_video(
                chat_id=chat_id,
                video=video_path,
                caption=caption,
                supports_streaming=True,
                progress=progress
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            return await self.send_video(chat_id, video_path, caption, progress_callback)
