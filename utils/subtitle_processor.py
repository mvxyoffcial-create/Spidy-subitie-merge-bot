import os
import asyncio
import subprocess
from pathlib import Path
from .progress_manager import ProgressManager

class SubtitleProcessor:
    def __init__(self, config):
        self.config = config
        self.active_jobs = {}
        
        # Check FFmpeg
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception("FFmpeg not installed")
            print(f"✅ FFmpeg: {result.stdout.splitlines()[0]}")
        except FileNotFoundError:
            raise Exception("FFmpeg not found")
    
    async def get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe"""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        stdout, _ = await process.communicate()
        try:
            return float(stdout.decode().strip())
        except ValueError:
            return 0.0
    
    async def burn_subtitles(self, video_path: str, subtitle_path: str, 
                            output_path: str, codec: str = "x264") -> ProgressManager:
        """Burn subtitles into video"""
        job_id = f"job_{int(asyncio.get_event_loop().time())}"
        video_size = os.path.getsize(video_path)
        progress = ProgressManager(video_size, "Burning Subtitles")
        self.active_jobs[job_id] = progress
        
        try:
            # Get duration for progress
            total_duration = await self.get_video_duration(video_path)
            
            # Escape subtitle path
            sub_path = subtitle_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            
            # Choose encoder
            encoder = "libx264" if codec == "x264" else "libx265"
            
            # Build FFmpeg command
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles={sub_path}",
                "-c:v", encoder,
                "-preset", "ultrafast",
                "-crf", "23",
                "-c:a", "copy",
                "-threads", "0",
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                "-nostats",
                output_path
            ]
            
            print(f"🎬 Running: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            last_update = 0
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode('utf-8', errors='ignore').strip()
                
                if "out_time_ms=" in line_str and total_duration > 0:
                    try:
                        time_ms = float(line_str.split("=")[1])
                        current_secs = time_ms / 1_000_000
                        percent = min((current_secs / total_duration) * 100, 100.0)
                        
                        # Update progress
                        current_bytes = int((percent / 100) * video_size)
                        await progress.update(current_bytes)
                        
                    except Exception:
                        pass
            
            await process.wait()
            
            if process.returncode != 0:
                raise Exception("FFmpeg encoding failed")
            
            progress.complete()
            return progress
            
        except Exception as e:
            progress.error_message = str(e)
            raise
        finally:
            self.active_jobs.pop(job_id, None)
