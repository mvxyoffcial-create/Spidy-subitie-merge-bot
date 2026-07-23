FROM python:3.10-slim

WORKDIR /app

# Install FFmpeg and all dependencies with full codec support
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavcodec-extra \
    libavformat-extra \
    libavfilter-extra \
    libavdevice-extra \
    libavutil-extra \
    libpostproc-extra \
    libswresample-extra \
    libswscale-extra \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Verify FFmpeg installation
RUN ffmpeg -version && echo "✅ FFmpeg installed successfully"

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p temp/input temp/output temp/cache sessions

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FFMPEG_THREADS=4

# Run the bot
CMD ["python", "bot.py"]
