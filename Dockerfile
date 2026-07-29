FROM n8nio/n8n:1.90.0

USER root

# Install Python + FFmpeg
RUN apk add --no-cache python3 py3-pip ffmpeg

# Create virtual env to avoid conflict
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install in venv - no conflict
RUN pip install --no-cache-dir edge-tts moviepy Pillow requests

USER node

USER node

ENV N8N_BASIC_AUTH_ACTIVE=true
ENV DB_TYPE=postgresdb
