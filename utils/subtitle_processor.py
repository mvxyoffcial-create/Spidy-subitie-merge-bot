import os
import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple
from .progress_manager import ProgressManager

class SubtitleProcessor:
    def __init__(self, config):
        self.config = config
        self.temp_dir = config.TEMP_DIR
        self.input_dir = config.INPUT_DIR
        self.output_dir = config.OUTPUT_DIR
        self.cache_dir = config.CACHE_DIR
        
        # Create directories
        self.config.setup_directories()
        
        # Processing queue
        self.active_jobs = {}
        self.job_counter = 0
    
    async def process_video(self, video_path: str, subtitle_path: str, 
                           output_name: str = None, job_id: str = None) -> Tuple[str, ProgressManager]:
        """
        Hard burn subtitles into video with progress tracking
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if not os.path.exists(subtitle_path):
            raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
        
        # Generate job ID if not provided
        if not job_id:
            self.job_counter += 1
            job_id = f"job_{self.job_counter}_{int(asyncio.get_event_loop().time())}"
        
        # Generate output filename
        if not output_name:
            base_name = Path(video_path).stem
            output_name = f"{base_name}_hardsub_{job_id}.mp4"
        
        output_path = os.path.join(self.output_dir, output_name)
        
        # Get file sizes for progress tracking
        video_size = os.path.getsize(video_path)
        subtitle_size = os.path.getsize(subtitle_path)
        total_size = video_size + subtitle_size
        
        # Create progress manager
        progress = ProgressManager(total_size, job_id)
        self.active_jobs[job_id] = progress
        
        try:
            # Process with FFmpeg
            await self._run_ffmpeg(video_path, subtitle_path, output_path, progress)
            
            # Mark as complete
            progress.complete()
            
            # Verify output exists
            if not os.path.exists(output_path):
                raise Exception("Output file was not created successfully")
            
            return output_path, progress
            
        except Exception as e:
            progress.set_error(str(e))
            raise
        finally:
            # Clean up active job reference
            self.active_jobs.pop(job_id, None)
    
    async def _run_ffmpeg(self, video_path: str, subtitle_path: str, 
                         output_path: str, progress: ProgressManager):
        """
        Run FFmpeg with progress tracking for ultra-fast processing
        """
        progress.set_stage("Preparing FFmpeg")
        
        # Prepare subtitle filter
        subtitle_filter = f"subtitles={subtitle_path}:force_style='Fontsize=24,OutlineColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=20'"
        
        # Build FFmpeg command for ultra-fast processing
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf', subtitle_filter,
            '-c:v', 'libx264',
            '-preset', self.config.ENCODING_PRESET,
            '-threads', str(self.config.FFMPEG_THREADS),
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-progress', 'pipe:1',
            '-stats',
            '-y',
            output_path
        ]
        
        # Update progress stage
        progress.set_stage("Encoding video")
        await progress.update(0, "Encoding video")
        
        # Start FFmpeg process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Get total duration for accurate progress
        total_duration = await self._get_video_duration(video_path)
        last_progress = 0
        
        # Read progress from FFmpeg output
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            
            line = line.decode('utf-8', errors='ignore').strip()
            
            # Parse FFmpeg progress
            if 'out_time=' in line:
                try:
                    time_str = line.split('=')[1].strip()
                    if ':' in time_str:
                        # Parse time in HH:MM:SS.milliseconds format
                        parts = time_str.split(':')
                        if len(parts) == 3:
                            hours = float(parts[0])
                            minutes = float(parts[1])
                            seconds = float(parts[2])
                            current_time = hours * 3600 + minutes * 60 + seconds
                            
                            if total_duration > 0:
                                progress_percent = min(100, int((current_time / total_duration) * 100))
                                
                                # Update progress based on video processing
                                if progress_percent > last_progress:
                                    bytes_processed = int((progress_percent - last_progress) / 100 * progress.total_size)
                                    await progress.update(bytes_processed, "Encoding video")
                                    last_progress = progress_percent
                except:
                    pass
            
            # Look for other progress indicators
            elif 'frame=' in line and 'fps=' in line:
                # This indicates active processing
                if progress.get_percentage() < 50:  # If still early in processing
                    # Simulate progress for large files where FFmpeg progress might not be reliable
                    await progress.update(1024 * 1024, "Processing")  # 1MB chunks
                    await asyncio.sleep(0.01)  # Prevent excessive CPU usage
        
        # Wait for process to complete
        await process.wait()
        
        if process.returncode != 0:
            stderr = await process.stderr.read()
            error_msg = stderr.decode('utf-8', errors='ignore')
            raise Exception(f"FFmpeg encoding failed: {error_msg}")
        
        # Ensure progress is at 100%
        progress.complete()
    
    async def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds using FFprobe"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                duration = float(stdout.decode().strip())
                return duration
            else:
                return 0
        except:
            return 0
    
    async def cleanup(self, *paths):
        """Clean up temporary files"""
        for path in paths:
            if path and os.path.exists(path):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                except Exception as e:
                    print(f"Cleanup error for {path}: {e}")
    
    def get_job_progress(self, job_id: str) -> Optional[ProgressManager]:
        """Get progress for a specific job"""
        return self.active_jobs.get(job_id)
