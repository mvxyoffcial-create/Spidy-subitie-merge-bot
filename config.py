import os
import psutil

class Config:
    # Bot Configuration
    BOT_TOKEN = "8638900175:AAHVl95mRb8Rjmut9CwnXHpERSIQh11xpVQ"
    
    # Telegram API Configuration
    API_ID = 36282056
    API_HASH = "3a948acece533f362b4c90b2b3c14b60"
    
    # File limits
    MAX_FILE_SIZE = 2147483648  # 2GB
    MAX_VIDEO_DURATION = 7200
    MAX_SUBTITLE_SIZE = 50 * 1024 * 1024
    
    # Directories
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TEMP_DIR = os.path.join(BASE_DIR, 'temp')
    OUTPUT_DIR = os.path.join(TEMP_DIR, 'output')
    SESSIONS_DIR = os.path.join(BASE_DIR, 'sessions')
    
    # FFmpeg settings
    FFMPEG_THREADS = os.cpu_count() or 4
    ENCODING_PRESET = 'ultrafast'
    CRF = 23
    
    # Supported formats
    SUPPORTED_SUB_FORMATS = ['.srt', '.ass', '.ssa', '.vtt', '.sub']
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.m4v', '.wmv']
    
    # Web server port
    PORT = int(os.getenv("PORT", "8000"))
    
    @classmethod
    def setup_directories(cls):
        for directory in [cls.TEMP_DIR, cls.OUTPUT_DIR, cls.SESSIONS_DIR]:
            os.makedirs(directory, exist_ok=True)
