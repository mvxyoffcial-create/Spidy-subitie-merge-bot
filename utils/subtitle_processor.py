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
        
        # Check if FFmpeg is available
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """Check if FFmpeg is installed and working"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception("FFmpeg is not installed or not working")
            print(f"✅ FFmpeg version: {result.stdout.splitlines()[0]}")
        except FileNotFoundError:
            raise Exception("FFmpeg not found. Please install FFmpeg.")
    
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
        
        # Fix subtitle path for FFmpeg (escape special characters)
        subtitle_path_escaped = subtitle_path.replace("'", "'\\''")
        
        # Prepare subtitle filter with better styling
        subtitle_filter = (
            f"subtitles='{subtitle_path_escaped}':"
            f"force_style='Fontsize=22,"
            f"OutlineColour=&H80000000,"
            f"BorderStyle=4,"
            f"Outline=2,"
            f"Shadow=1,"
            f"MarginV=30,"
            f"FontName=Arial,"
            f"PrimaryColour=&H00FFFFFF,"
            f"SecondaryColour=&H00FFFF00,"
            f"FontBold=1'"
        )
        
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
        
        print(f"🎬 Running FFmpeg command: {' '.join(cmd)}")
        
        # Update progress stage
        progress.set_stage("Encoding video")
        await progress.update(0, "Encoding video")
        
        # Get total duration for accurate progress
        total_duration = await self._get_video_duration(video_path)
        print(f"📹 Video duration: {total_duration} seconds")
        
        # Start FFmpeg process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        last_progress = 0
        
        # Read progress from FFmpeg output
        stderr_lines = []
        
        while True:
            # Read stderr for progress
            line = await process.stderr.readline()
            if not line:
                break
            
            line_str = line.decode('utf-8', errors='ignore').strip()
            stderr_lines.append(line_str)
            
            # Print debug info
            print(f"FFmpeg: {line_str}")
            
            # Parse FFmpeg progress
            if 'out_time=' in line_str:
                try:
                    time_str = line_str.split('=')[1].strip()
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
                except Exception as e:
                    print(f"Error parsing time: {e}")
            
            # Check for errors
            if 'error' in line_str.lower() or 'failed' in line_str.lower():
                print(f"⚠️ FFmpeg error: {line_str}")
        
        # Wait for process to complete
        await process.wait()
        
        # Check if FFmpeg failed
        if process.returncode != 0:
            # Get stderr output
            stderr_text = '\n'.join(stderr_lines)
            print(f"❌ FFmpeg failed with return code: {process.returncode}")
            print(f"Stderr output: {stderr_text}")
            
            # Check for specific errors
            if 'Permission denied' in stderr_text:
                raise Exception(f"FFmpeg permission error: {stderr_text[:200]}")
            elif 'No such file' in stderr_text:
                raise Exception(f"FFmpeg file not found: {stderr_text[:200]}")
            elif 'Invalid argument' in stderr_text:
                raise Exception(f"FFmpeg invalid argument: {stderr_text[:200]}")
            else:
                raise Exception(f"FFmpeg encoding failed:\n{stderr_text[:500]}")
        
        # Ensure progress is at 100%
        progress.complete()
        print("✅ FFmpeg encoding completed successfully")
    
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
                duration_str = stdout.decode().strip()
                if duration_str:
                    return float(duration_str)
            return 0
        except Exception as e:
            print(f"Error getting duration: {e}")
            return 0
    
    def get_job_progress(self, job_id: str) -> Optional[ProgressManager]:
        """Get progress for a specific job"""
        return self.active_jobs.get(job_id)
    
    def get_all_jobs(self) -> dict:
        """Get all active jobs"""
        return self.active_jobs.copy()
    
    async def cleanup(self, *paths):
        """Clean up temporary files"""
        for path in paths:
            if path and os.path.exists(path):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                        print(f"🧹 Cleaned up file: {path}")
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                        print(f"🧹 Cleaned up directory: {path}")
                except Exception as e:
                    print(f"Cleanup error for {path}: {e}")
