FROM python:3.10-slim

WORKDIR /app

# Install FFmpeg and dependencies with full codec support
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavcodec-extra \
    libavformat-extra \
    libavfilter-extra \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p temp/input temp/output temp/cache

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TEMP_DIR=/app/temp
ENV TZ=UTC

# Run the bot
CMD ["python", "bot.py"]
