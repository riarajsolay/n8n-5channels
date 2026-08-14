FROM n8nio/n8n:latest

# root user loki velli ffmpeg install chestunnam
USER root
RUN apk update && apk add --no-cache ffmpeg

# malli normal user ki vacheyali
USER node



