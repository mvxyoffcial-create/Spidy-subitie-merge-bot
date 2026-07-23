import time
import asyncio
from typing import Optional, Callable

class ProgressManager:
    def __init__(self, total_size: int, job_id: str, operation: str = "Processing"):
        self.job_id = job_id
        self.total_size = total_size
        self.processed_size = 0
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 1.0
        self.status = "initializing"
        self.current_stage = operation
        self.error_message = None
        self.is_complete = False
        self.operation = operation
        
        # Track processing metrics
        self.estimated_speed = 0
        self.speed_samples = []
        self.max_samples = 10
        
        # For speed calculation
        self.last_size = 0
        self.last_time = time.time()
        
        # Callback for progress updates
        self.callback = None
    
    async def update(self, processed_bytes: int, stage: str = None):
        """Update progress and trigger callback"""
        self.processed_size += processed_bytes
        
        if stage:
            self.current_stage = stage
        
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            self.last_update = current_time
            percentage = self.get_percentage()
            speed = self.get_speed()
            
            # Update speed samples
            if speed > 0:
                self.speed_samples.append(speed)
                if len(self.speed_samples) > self.max_samples:
                    self.speed_samples.pop(0)
                self.estimated_speed = sum(self.speed_samples) / len(self.speed_samples)
            
            # Trigger callback
            if self.callback:
                try:
                    await self.callback(percentage, self.estimated_speed, self.current_stage)
                except Exception as e:
                    print(f"Callback error: {e}")
    
    def get_percentage(self) -> int:
        """Get progress percentage"""
        if self.total_size <= 0:
            return 0
        return min(100, int((self.processed_size / self.total_size) * 100))
    
    def get_speed(self) -> float:
        """Get processing speed in MB/s"""
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return 0
        speed_mb = (self.processed_size / 1024 / 1024) / elapsed
        return speed_mb
    
    def get_eta(self) -> Optional[int]:
        """Get estimated time remaining in seconds"""
        if self.estimated_speed <= 0:
            return None
        
        remaining_mb = (self.total_size - self.processed_size) / 1024 / 1024
        if remaining_mb <= 0:
            return 0
        
        return int(remaining_mb / self.estimated_speed)
    
    def get_progress_bar(self, width: int = 20) -> str:
        """Generate progress bar string with blocks"""
        percentage = self.get_percentage()
        filled = int(width * percentage / 100)
        bar = '█' * filled + '░' * (width - filled)
        return bar
    
    def get_progress_text(self) -> str:
        """Get complete progress status message like the screenshot"""
        percentage = self.get_percentage()
        bar = self.get_progress_bar(20)
        speed = self.estimated_speed or self.get_speed()
        eta = self.get_eta()
        elapsed = self.get_elapsed_time()
        
        # Format sizes
        processed_mb = self.processed_size / 1024 / 1024
        total_mb = self.total_size / 1024 / 1024
        processed_str = self.format_size(self.processed_size)
        total_str = self.format_size(self.total_size)
        
        # Build status message
        status = f"📊 **Task Running:** {self.current_stage}\n\n"
        status += f"**1. Download:**\n"
        status += f"[ ] {percentage}%\n"
        status += f"`{bar}`\n\n"
        status += f"**Processed:** {processed_str}\n"
        status += f"**Size:** {total_str}\n"
        
        if speed > 0:
            status += f"**Speed:** {speed:.1f} MB/s\n"
        else:
            status += f"**Speed:** 0 B/s\n"
        
        if eta is not None and eta > 0:
            minutes = eta // 60
            seconds = eta % 60
            status += f"**ETA:** {minutes:02d}:{seconds:02d}\n"
        elif eta == 0:
            status += f"**ETA:** -\n"
        else:
            status += f"**ETA:** Calculating...\n"
        
        status += f"**Elapsed:** {elapsed}\n"
        status += f"**Upload:** Telegram\n"
        status += f"**Engine:** TDLib v1.8.66"
        
        if self.error_message:
            status += f"\n\n❌ **Error:** {self.error_message}"
        
        return status
    
    def format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes >= 1024 * 1024 * 1024:
            return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"
        elif size_bytes >= 1024 * 1024:
            return f"{size_bytes / 1024 / 1024:.1f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes} B"
    
    def get_status_message(self) -> str:
        """Get complete status message"""
        return self.get_progress_text()
    
    def set_stage(self, stage: str):
        """Update current processing stage"""
        self.current_stage = stage
    
    def set_error(self, error_message: str):
        """Set error message"""
        self.error_message = error_message
        self.status = "error"
    
    def complete(self):
        """Mark process as complete"""
        self.is_complete = True
        self.current_stage = "Complete"
        self.processed_size = self.total_size
    
    def get_elapsed_time(self) -> str:
        """Get elapsed time as string"""
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes:02d}:{seconds:02d}"
