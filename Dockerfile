FROM n8nio/n8n:1.90.0

USER root

# Install Python + FFmpeg + Build tools (Alpine fix)
RUN apk update && apk add --no-cache \
    python3 \
    py3-pip \
    python3-dev \
    py3-wheel \
    ffmpeg \
    build-base \
    libffi-dev \
    openssl-dev \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    gcc \
    musl-dev

# Upgrade pip
RUN python3 -m pip install --upgrade pip setuptools wheel --break-system-packages

# Install Python libs one by one - 100% FREE
RUN pip3 install --no-cache-dir --break-system-packages edge-tts
RUN pip3 install --no-cache-dir --break-system-packages moviepy Pillow
RUN pip3 install --no-cache-dir --break-system-packages requests groq openai
RUN pip3 install --no-cache-dir --break-system-packages google-api-python-client google-auth-httplib2 google-auth-oauthlib
# instagrapi heavy - optional
RUN pip3 install --no-cache-dir --break-system-packages instagrapi facebook-sdk || echo "optional skip"

USER node

ENV N8N_BASIC_AUTH_ACTIVE=true
ENV DB_TYPE=postgresdb
