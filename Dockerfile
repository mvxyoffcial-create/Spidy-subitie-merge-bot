#!/bin/bash

# Create a working Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.10-slim

WORKDIR /app

# Install FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Verify FFmpeg
RUN ffmpeg -version

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Create directories
RUN mkdir -p temp/input temp/output temp/cache sessions

# Run
CMD ["python", "bot.py"]
EOF

# Deploy
git add Dockerfile
git commit -m "Fix Dockerfile - remove invalid packages"
git push
