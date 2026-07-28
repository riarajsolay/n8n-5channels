FROM n8nio/n8n:1.90.0
USER root
# Install Python + FFmpeg (video making ki must) - FREE
RUN apk add --no-cache python3 py3-pip ffmpeg
# Install Python libs - 100% FREE tools
RUN pip3 install --no-cache-dir \
    edge-tts \
    moviepy==1.0.3 \
    Pillow \
    instagrapi \
    google-api-python-client \
    google-auth-httplib2 \
    google-auth-oauthlib \
    facebook-sdk \
    requests \
    groq \
    openai
USER node
# Keep your existing envs
ENV N8N_BASIC_AUTH_ACTIVE=true
ENV DB_TYPE=postgresdb
