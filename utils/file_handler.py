import os
import asyncio
import aiofiles
from typing import Optional, Tuple, Callable, Awaitable
from pyrogram import Client
from pyrogram.errors import RPCError, FloodWait
import logging

logger = logging.getLogger(__name__)

class FileHandler:
    def __init__(self, config):
        self.config = config
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Pyrogram client for large file handling"""
        if not self.client:
            self.client = Client(
                self.config.BOT_SESSION,
                api_id=self.config.API_ID,
                api_hash=self.config.API_HASH,
                bot_token=self.config.BOT_TOKEN,
                workdir=self.config.SESSIONS_DIR
            )
    
    async def start(self):
        """Start the Pyrogram client"""
        if self.client and not self.client.is_connected:
            await self.client.start()
            logger.info("Pyrogram client started successfully")
    
    async def stop(self):
        """Stop the Pyrogram client"""
        if self.client and self.client.is_connected:
            await self.client.stop()
            logger.info("Pyrogram client stopped")
    
    async def download_file(self, file_id: str, output_path: str, 
                           progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None) -> str:
        """
        Download a large file using Pyrogram with progress tracking
        """
        try:
            await self.start()
            
            async def progress(current, total):
                if progress_callback:
                    await progress_callback(current, total)
            
            # Download file with progress
            await self.client.download_media(
                message=file_id,
                file_name=output_path,
                progress=progress
            )
            
            if not os.path.exists(output_path):
                raise Exception("File download failed")
            
            return output_path
            
        except FloodWait as e:
            wait_time = e.value
            logger.warning(f"Flood wait: {wait_time} seconds")
            await asyncio.sleep(wait_time)
            # Retry after wait
            return await self.download_file(file_id, output_path, progress_callback)
            
        except RPCError as e:
            logger.error(f"RPC Error: {e}")
            raise
    
    async def upload_file(self, file_path: str, caption: str = "",
                         progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None) -> dict:
        """
        Upload a large file using Pyrogram with progress tracking
        """
        try:
            await self.start()
            
            # Get file info
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            async def progress(current, total):
                if progress_callback:
                    await progress_callback(current, total)
            
            # Upload file with progress
            result = await self.client.send_document(
                chat_id="me",  # Send to saved messages first
                document=file_path,
                caption=caption,
                progress=progress,
                file_name=file_name
            )
            
            return {
                'file_id': result.document.file_id,
                'file_size': file_size,
                'file_name': file_name,
                'message_id': result.id
            }
            
        except FloodWait as e:
            wait_time = e.value
            logger.warning(f"Flood wait: {wait_time} seconds")
            await asyncio.sleep(wait_time)
            # Retry after wait
            return await self.upload_file(file_path, caption, progress_callback)
            
        except RPCError as e:
            logger.error(f"RPC Error: {e}")
            raise
    
    async def get_file_info(self, file_id: str) -> dict:
        """Get file information using Pyrogram"""
        try:
            await self.start()
            message = await self.client.get_messages("me", message_ids=int(file_id))
            return {
                'file_id': message.document.file_id,
                'file_size': message.document.file_size,
                'file_name': message.document.file_name,
                'mime_type': message.document.mime_type
            }
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return None
    
    async def send_video_to_user(self, chat_id: int, video_path: str, 
                                caption: str = "",
                                progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None) -> dict:
        """
        Send video file to user with progress tracking
        """
        try:
            await self.start()
            
            async def progress(current, total):
                if progress_callback:
                    await progress_callback(current, total)
            
            # Send video
            result = await self.client.send_video(
                chat_id=chat_id,
                video=video_path,
                caption=caption,
                progress=progress,
                supports_streaming=True,
                file_name=os.path.basename(video_path)
            )
            
            return {
                'message_id': result.id,
                'file_id': result.video.file_id,
                'file_size': result.video.file_size
            }
            
        except FloodWait as e:
            wait_time = e.value
            logger.warning(f"Flood wait: {wait_time} seconds")
            await asyncio.sleep(wait_time)
            return await self.send_video_to_user(chat_id, video_path, caption, progress_callback)
            
        except RPCError as e:
            logger.error(f"RPC Error: {e}")
            raise
