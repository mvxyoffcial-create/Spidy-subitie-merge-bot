import time
from typing import Optional

class ProgressManager:
    def __init__(self, total_size: int, operation: str = "Processing"):
        self.total_size = total_size
        self.processed_size = 0
        self.operation = operation
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 2.0  # Update every 2 seconds
        self.is_complete = False
        self.error_message = None
        
        # Speed calculation
        self.speed_samples = []
        self.max_samples = 5
        self.estimated_speed = 0
        
        # Callback
        self.callback = None
    
    async def update(self, current: int, total: int = None, stage: str = None):
        """Update progress"""
        if total:
            self.total_size = total
        self.processed_size = current
        
        if stage:
            self.operation = stage
        
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            self.last_update = current_time
            percentage = self.get_percentage()
            speed = self.get_speed()
            
            if self.callback:
                try:
                    await self.callback(percentage, speed, self.operation)
                except Exception as e:
                    print(f"Callback error: {e}")
    
    def get_percentage(self) -> float:
        """Get progress percentage"""
        if self.total_size <= 0:
            return 0
        return min(100, (self.processed_size / self.total_size) * 100)
    
    def get_speed(self) -> float:
        """Get speed in MB/s"""
        elapsed = time.time() - self.start_time
        if elapsed <= 0 or self.processed_size <= 0:
            return 0
        speed = (self.processed_size / 1024 / 1024) / elapsed
        
        # Smooth speed
        self.speed_samples.append(speed)
        if len(self.speed_samples) > self.max_samples:
            self.speed_samples.pop(0)
        return sum(self.speed_samples) / len(self.speed_samples)
    
    def get_eta(self) -> Optional[int]:
        """Get ETA in seconds"""
        speed = self.get_speed()
        if speed <= 0:
            return None
        remaining = self.total_size - self.processed_size
        if remaining <= 0:
            return 0
        return int((remaining / 1024 / 1024) / speed)
    
    def get_progress_bar(self, width: int = 20) -> str:
        """Generate progress bar"""
        percentage = self.get_percentage()
        filled = int(width * percentage / 100)
        return '█' * filled + '░' * (width - filled)
    
    def format_size(self, size_bytes: int) -> str:
        """Format file size"""
        if size_bytes >= 1024 * 1024 * 1024:
            return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"
        elif size_bytes >= 1024 * 1024:
            return f"{size_bytes / 1024 / 1024:.1f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes} B"
    
    def get_status_text(self) -> str:
        """Get complete status text"""
        percentage = self.get_percentage()
        bar = self.get_progress_bar(20)
        speed = self.get_speed()
        eta = self.get_eta()
        elapsed = self.get_elapsed_time()
        
        status = f"📊 **{self.operation}**\n\n"
        status += f"`{bar}` **{percentage:.1f}%**\n\n"
        status += f"📦 **Size:** {self.format_size(self.processed_size)} / {self.format_size(self.total_size)}\n"
        
        if speed > 0:
            status += f"⚡ **Speed:** {speed:.2f} MB/s\n"
        else:
            status += f"⚡ **Speed:** Calculating...\n"
        
        if eta is not None:
            if eta > 0:
                minutes = eta // 60
                seconds = eta % 60
                status += f"⏱️ **ETA:** {minutes:02d}:{seconds:02d}\n"
            else:
                status += f"⏱️ **ETA:** Almost done!\n"
        else:
            status += f"⏱️ **ETA:** Calculating...\n"
        
        status += f"⏱️ **Elapsed:** {elapsed}"
        
        if self.error_message:
            status += f"\n\n❌ **Error:** {self.error_message}"
        
        return status
    
    def get_elapsed_time(self) -> str:
        """Get elapsed time"""
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def complete(self):
        """Mark as complete"""
        self.is_complete = True
        self.processed_size = self.total_size
