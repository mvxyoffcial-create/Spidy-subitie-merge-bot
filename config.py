import os
import psutil

class Config:
    # Bot Configuration - Hardcoded for private repo
    BOT_TOKEN = "8638900175:AAHVl95mRb8Rjmut9CwnXHpERSIQh11xpVQ"
    
    # Telegram API Configuration - Hardcoded
    API_ID = 36282056
    API_HASH = "3a948acece533f362b4c90b2b3c14b60"
    
    # File limits
    MAX_FILE_SIZE = 2147483648  # 2GB in bytes
    MAX_VIDEO_DURATION = 7200  # 2 hours in seconds
    MAX_SUBTITLE_SIZE = 50 * 1024 * 1024  # 50MB for subtitles
    
    # Directory paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TEMP_DIR = os.path.join(BASE_DIR, 'temp')
    INPUT_DIR = os.path.join(TEMP_DIR, 'input')
    OUTPUT_DIR = os.path.join(TEMP_DIR, 'output')
    CACHE_DIR = os.path.join(TEMP_DIR, 'cache')
    SESSIONS_DIR = os.path.join(BASE_DIR, 'sessions')
    
    # FFmpeg settings for ultra-fast processing
    FFMPEG_THREADS = os.cpu_count() or 4
    ENCODING_PRESET = 'ultrafast'
    
    # Supported formats
    SUPPORTED_SUB_FORMATS = ['.srt', '.ass', '.ssa', '.vtt', '.sub']
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mkv', '.mov', '.flv', '.webm', '.m4v', '.wmv', '.mpg']
    
    # Progress update interval (seconds)
    PROGRESS_UPDATE_INTERVAL = 1.0
    
    # Maximum concurrent processing jobs
    MAX_CONCURRENT_JOBS = 1
    
    # Session name
    BOT_SESSION = 'subtitle_bot'
    
    # Create directories if they don't exist
    @classmethod
    def setup_directories(cls):
        for directory in [cls.TEMP_DIR, cls.INPUT_DIR, cls.OUTPUT_DIR, cls.CACHE_DIR, cls.SESSIONS_DIR]:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created directory: {directory}")
    
    @classmethod
    def get_file_size_mb(cls, file_size_bytes: int) -> float:
        """Convert bytes to MB"""
        return file_size_bytes / 1024 / 1024
    
    @classmethod
    def get_file_size_gb(cls, file_size_bytes: int) -> float:
        """Convert bytes to GB"""
        return file_size_bytes / 1024 / 1024 / 1024
    
    @classmethod
    def get_system_info(cls):
        """Get system information"""
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_total': psutil.virtual_memory().total / 1024 / 1024 / 1024,
            'memory_available': psutil.virtual_memory().available / 1024 / 1024 / 1024,
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent
        }
    
    @classmethod
    def validate_config(cls):
        """Validate all configuration settings"""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is missing")
        if not cls.API_ID:
            errors.append("API_ID is missing")
        if not cls.API_HASH:
            errors.append("API_HASH is missing")
        if cls.MAX_FILE_SIZE <= 0:
            errors.append("MAX_FILE_SIZE must be greater than 0")
        if cls.FFMPEG_THREADS <= 0:
            errors.append("FFMPEG_THREADS must be greater than 0")
        
        # Check if directories are writable
        for directory in [cls.TEMP_DIR, cls.INPUT_DIR, cls.OUTPUT_DIR, cls.CACHE_DIR, cls.SESSIONS_DIR]:
            try:
                os.makedirs(directory, exist_ok=True)
                if not os.access(directory, os.W_OK):
                    errors.append(f"Directory not writable: {directory}")
            except Exception as e:
                errors.append(f"Cannot create directory {directory}: {e}")
        
        if errors:
            error_msg = "\n".join(errors)
            raise ValueError(f"Configuration validation failed:\n{error_msg}")
        
        return True
    
    @classmethod
    def print_config(cls):
        """Print current configuration (hide sensitive data)"""
        print("=" * 50)
        print("📋 BOT CONFIGURATION")
        print("=" * 50)
        print(f"🤖 Bot Token: {cls.BOT_TOKEN[:15]}...{cls.BOT_TOKEN[-5:]}")
        print(f"📡 API ID: {cls.API_ID}")
        print(f"🔑 API Hash: {cls.API_HASH[:10]}...{cls.API_HASH[-10:]}")
        print(f"📦 Max File Size: {cls.get_file_size_gb(cls.MAX_FILE_SIZE):.1f}GB")
        print(f"⏱️ Max Video Duration: {cls.MAX_VIDEO_DURATION // 60} minutes")
        print(f"💾 Max Subtitle Size: {cls.MAX_SUBTITLE_SIZE / 1024 / 1024:.0f}MB")
        print(f"📁 Temp Directory: {cls.TEMP_DIR}")
        print(f"⚡ FFmpeg Threads: {cls.FFMPEG_THREADS}")
        print(f"🎯 Encoding Preset: {cls.ENCODING_PRESET}")
        print(f"📝 Supported Sub Formats: {', '.join(cls.SUPPORTED_SUB_FORMATS)}")
        print(f"🎬 Supported Video Formats: {', '.join(cls.SUPPORTED_VIDEO_FORMATS)}")
        print("=" * 50)
        
        # System info
        sys_info = cls.get_system_info()
        print(f"💻 CPU Cores: {sys_info['cpu_count']}")
        print(f"🧠 CPU Usage: {sys_info['cpu_percent']}%")
        print(f"💾 Memory: {sys_info['memory_available']:.1f}GB / {sys_info['memory_total']:.1f}GB ({sys_info['memory_percent']}%)")
        print(f"💿 Disk Usage: {sys_info['disk_usage']}%")
        print("=" * 50)
