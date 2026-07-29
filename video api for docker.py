
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
import edge_tts
from moviepy.editor import *
import os
import uuid

app = FastAPI(title="Telugu Video Factory API - Unlimited Channels")

class VideoRequest(BaseModel):
    channel: str
    topic: str
    voice: str = "te-IN-ShrutiNeural"
    id: str = "1"

@app.get("/")
def home():
    return {"status": "🔥 Telugu Video Factory API Running", "channels": "Unlimited (6 to 50+)", "endpoint": "/generate"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate")
async def generate_video(req: VideoRequest):
    safe = req.channel.replace(" ", "_").replace("/", "_")
    uid = str(uuid.uuid4())[:6]
    audio_file = f"/tmp/{safe}_{uid}.mp3"
    video_file = f"/tmp/{safe}_{uid}.mp4"
    
    print(f"🎬 [{req.channel}] Topic: {req.topic[:50]}...")
    
    # 1. Telugu Voice
    try:
        communicate = edge_tts.Communicate(req.topic, req.voice)
        await communicate.save(audio_file)
    except Exception as e:
        return {"error": f"Audio failed: {str(e)}"}
    
    # 2. Video 1080x1920
    try:
        audio = AudioFileClip(audio_file)
        bg = ColorClip(size=(1080, 1920), color=(15, 23, 42), duration=audio.duration)
        txt = TextClip(req.topic[:150], fontsize=55, color='white', font='DejaVu-Sans-Bold', method='caption', size=(900, None), align='center')
        txt = txt.set_position('center').set_duration(audio.duration)
        watermark = TextClip(req.channel, fontsize=35, color='yellow', font='DejaVu-Sans-Bold')
        watermark = watermark.set_position(('center', 150)).set_duration(audio.duration)
        final = CompositeVideoClip([bg, txt, watermark]).set_audio(audio)
        final.write_videofile(video_file, fps=24, codec='libx264', audio_codec='aac', verbose=False, logger=None)
    except Exception as e:
        return {"error": f"Video failed: {str(e)}"}
    
    # Return video file
    return FileResponse(video_file, filename=f"{safe}.mp4", media_type="video/mp4")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
