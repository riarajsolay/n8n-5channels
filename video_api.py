
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import edge_tts
import uuid
import os
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import AudioFileClip, ColorClip, ImageClip, CompositeVideoClip

app = FastAPI(title="Telugu Video Factory API")

class VideoRequest(BaseModel):
    channel: str
    topic: str
    voice: str = "te-IN-ShrutiNeural"
    id: str = "1"

def create_text_image(text, width=900, font_size=50, color=(255,255,255)):
    # Create text image with PIL (No ImageMagick needed)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    # Wrap text
    words = text.split()
    lines = []
    line = ""
    for w in words:
        test = line + " " + w if line else w
        if len(test) > 25:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    lines = lines[:6]  # Max 6 lines
    
    # Calculate height
    line_height = font_size + 15
    img_height = len(lines) * line_height + 60
    img = Image.new('RGBA', (width, img_height), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    y = 10
    for l in lines:
        draw.text((20, y), l, font=font, fill=color, stroke_width=2, stroke_fill=(0,0,0))
        y += line_height
    path = f"/tmp/text_{uuid.uuid4().hex[:6]}.png"
    img.save(path)
    return path, img_height

@app.get("/")
def home():
    return {"status": "Telugu Video Factory API Running OK", "channels": "Unlimited"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate")
async def generate_video(req: VideoRequest):
    safe = "".join([c for c in req.channel if c.isalnum() or c in "_-"])[:20]
    uid = uuid.uuid4().hex[:6]
    audio_file = f"/tmp/{safe}_{uid}.mp3"
    video_file = f"/tmp/{safe}_{uid}.mp4"
    
    print(f"Generating: {req.channel} - {req.topic[:40]}")
    
    # 1. Audio
    try:
        communicate = edge_tts.Communicate(req.topic, req.voice)
        await communicate.save(audio_file)
    except Exception as e:
        return {"error": f"Audio failed: {e}"}
    
    # 2. Video
    try:
        audio = AudioFileClip(audio_file)
        duration = max(5, audio.duration)
        
        bg = ColorClip(size=(1080, 1920), color=(15,23,42), duration=duration)
        
        # Channel watermark as image
        channel_img_path, _ = create_text_image(req.channel, width=800, font_size=60, color=(255,221,0))
        channel_clip = ImageClip(channel_img_path, duration=duration).set_position(('center', 200))
        
        # Main topic text
        topic_img_path, h = create_text_image(req.topic[:300], width=950, font_size=48, color=(255,255,255))
        topic_clip = ImageClip(topic_img_path, duration=duration).set_position(('center', 800))
        
        final = CompositeVideoClip([bg, channel_clip, topic_clip]).set_audio(audio)
        final.write_videofile(video_file, fps=24, codec='libx264', audio_codec='aac', verbose=False, logger=None)
        
        # Cleanup temp images
        try:
            os.remove(channel_img_path)
            os.remove(topic_img_path)
        except:
            pass
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Video failed: {e}"}
    
    return FileResponse(video_file, filename=f"{safe}.mp4", media_type="video/mp4")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
