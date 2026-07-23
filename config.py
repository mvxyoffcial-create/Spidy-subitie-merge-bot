import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is required")
    
    # Telegram API Configuration (for large file uploads)
    API_ID = os.getenv('API_ID')
    API_HASH = os.getenv('API_HASH')
    
    if not API_ID or not API_HASH:
        raise ValueError("API_ID and API_HASH are required for 2GB file uploads")
    
    # File limits
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 2147483648))  # 2GB in bytes
    MAX_VIDEO_DURATION = 7200  # 2 hours in seconds
    MAX_SUBTITLE_SIZE = 50 * 1024 * 1024  # 50MB for subtitles
    
    # Directory paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TEMP_DIR = os.getenv('TEMP_DIR', os.path.join(BASE_DIR, 'temp'))
    INPUT_DIR = os.path.join(TEMP_DIR, 'input')
    OUTPUT_DIR = os.path.join(TEMP_DIR, 'output')
    CACHE_DIR = os.path.join(TEMP_DIR, 'cache')
    SESSIONS_DIR = os.path.join(BASE_DIR, 'sessions')
    
    # FFmpeg settings for ultra-fast processing
    FFMPEG_THREADS = int(os.getenv('FFMPEG_THREADS', os.cpu_count() or 4))
    ENCODING_PRESET = os.getenv('ENCODING_PRESET', 'ultrafast')
    
    # Supported formats
    SUPPORTED_SUB_FORMATS = ['.srt', '.ass', '.ssa', '.vtt', '.sub']
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mkv', '.mov', '.flv', '.webm', '.m4v', '.wmv', '.mpg']
    
    # Progress update interval (seconds)
    PROGRESS_UPDATE_INTERVAL = 1.0
    
    # Maximum concurrent processing jobs
    MAX_CONCURRENT_JOBS = 1
    
    # Session name
    BOT_SESSION = os.getenv('BOT_SESSION', 'subtitle_bot')
    
    # Create directories if they don't exist
    @classmethod
    def setup_directories(cls):
        for directory in [cls.TEMP_DIR, cls.INPUT_DIR, cls.OUTPUT_DIR, cls.CACHE_DIR, cls.SESSIONS_DIR]:
            os.makedirs(directory, exist_ok=True)
    
    @classmethod
    def get_file_size_mb(cls, file_size_bytes: int) -> float:
        """Convert bytes to MB"""
        return file_size_bytes / 1024 / 1024
    
    @classmethod
    def get_file_size_gb(cls, file_size_bytes: int) -> float:
        """Convert bytes to GB"""
        return file_size_bytes / 1024 / 1024 / 1024
