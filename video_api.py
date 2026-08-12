from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid
import os
import requests
import base64
import re
import subprocess
import gc
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Telugu Video Factory API - Lightweight 10 Videos/Day")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

VOICE_PROFILES = {
    "young_female": {"voice": "anushka", "pace": 1.0},
    "young_male": {"voice": "abhilash", "pace": 1.0},
    "middle_female": {"voice": "manisha", "pace": 0.95},
    "middle_male": {"voice": "karun", "pace": 0.95},
    "old_female": {"voice": "manisha", "pace": 0.85},
    "old_male": {"voice": "karun", "pace": 0.85},
    "kid_female": {"voice": "vidya", "pace": 1.15},
    "kid_male": {"voice": "arya", "pace": 1.15},
}

class VideoRequest(BaseModel):
    channel: str
    topic: str
    voice: str = "anushka"
    id: str = "1"

def detect_characters_fast(script: str):
    """No API call - super fast, no RAM"""
    fallback = {}
    names = re.findall(r'([A-Za-z\u0C00-\u0C7F]+)\s*:', script)
    for n in names:
        n = n.strip()
        n_low = n.lower()
        if any(x in n_low for x in ['amma','avva','bomma','mother']): fallback[n] = {"gender":"female","age_group":"old"}
        elif any(x in n_low for x in ['thatha','nanna','father','tata']): fallback[n] = {"gender":"male","age_group":"old"}
        elif any(x in n_low for x in ['chinna','chintu','pilla','babu','pappu','kid']): fallback[n] = {"gender":"male","age_group":"kid"}
        elif n_low.endswith('a') or n_low in ['anushka','priya','sita','geeta','manisha','vidya']: fallback[n] = {"gender":"female","age_group":"young"}
        else: fallback[n] = {"gender":"male","age_group":"young"}
    return fallback

def get_voice_for_character(gender, age_group):
    key = f"{age_group}_{gender}"
    if gender == "male" and key.endswith("_female"): key = key.replace("_female", "_male")
    if gender == "female" and "_female" not in key: key = key.replace("_male", "_female") if "_male" in key else f"{age_group}_female"
    profile = VOICE_PROFILES.get(key)
    if not profile:
        return VOICE_PROFILES["young_female"] if gender == "female" else VOICE_PROFILES["young_male"]
    return profile

def generate_sarvam_audio(text, voice_name, pace, audio_file):
    url = "https://api.sarvam.ai/text-to-speech"
    headers = {"api-subscription-key": SARVAM_API_KEY}
    payload = {
        "inputs": [text],
        "target_language_code": "te-IN",
        "speaker": voice_name,
        "model": "bulbul:v3",
        "pace": pace,
        "speech_sample_rate": 22050
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    audio_b64 = data["audios"][0]
    with open(audio_file, "wb") as f:
        f.write(base64.b64decode(audio_b64))
    return True

def create_background_image(channel, topic, width=720, height=1280):
    """Single image - no moviepy clips - very low RAM"""
    img = Image.new('RGB', (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(img)
    try:
        font_channel = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
        font_topic = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)
    except:
        font_channel = ImageFont.load_default()
        font_topic = ImageFont.load_default()
    
    # Channel - top
    draw.text((width//2, 150), channel[:30], font=font_channel, fill=(255,221,0), anchor="mm")
    # Topic - middle with wrap
    words = topic[:250].split()
    lines = []
    line = ""
    for w in words:
        test = line + " " + w if line else w
        if len(test) > 28:
            lines.append(line)
            line = w
        else:
            line = test
    if line: lines.append(line)
    y = 400
    for l in lines[:8]:
        draw.text((width//2, y), l, font=font_topic, fill=(255,255,255), anchor="mm")
        y += 55
    
    path = f"/tmp/bg_{uuid.uuid4().hex[:6]}.png"
    img.save(path)
    return path

@app.get("/")
def home():
    return {"status": "Telugu Video Factory API Running OK - Lightweight", "channels": "Unlimited", "ram": "50MB Optimized", "daily_capacity": "10+ videos"}

@app.get("/health")
def health():
    return {"status": "ok", "memory": "optimized"}

@app.post("/generate")
async def generate_video(req: VideoRequest):
    safe = "".join([c for c in req.channel if c.isalnum() or c in "_-"])[:20]
    uid = uuid.uuid4().hex[:6]
    audio_file = f"/tmp/{safe}_{uid}_final.mp3"
    video_file = f"/tmp/{safe}_{uid}.mp4"
    list_file = f"/tmp/{safe}_{uid}_list.txt"
    
    print(f"Generating: {req.channel} - {req.topic[:40]}")
    temp_audios = []
    
    try:
        # 1. Fast character detection - no heavy API
        detected_chars = detect_characters_fast(req.topic)
        print(f"Detected: {detected_chars}")

        dialogues = []
        for line in req.topic.split('\n'):
            line = line.strip()
            if not line: continue
            if ':' in line and len(line.split(':')[0]) < 30:
                name, dia = line.split(':', 1)
                name = name.strip()
                info = detected_chars.get(name, {"gender":"female" if name.lower().endswith('a') else "male", "age_group":"young"})
                vp = get_voice_for_character(info['gender'], info['age_group'])
                dialogues.append((name, dia.strip(), vp))
            else:
                vp = VOICE_PROFILES["young_female"]
                dialogues.append(("Narrator", line, vp))

        if not dialogues:
            dialogues = [("Narrator", req.topic, VOICE_PROFILES["young_female"])]

        # 2. Generate each audio - one by one (low RAM)
        for idx, (char_name, dia_text, vp) in enumerate(dialogues):
            tmp = f"/tmp/{safe}_{uid}_{idx}.mp3"
            print(f"Audio {idx+1}/{len(dialogues)} for {char_name} ({vp['voice']})")
            try:
                if SARVAM_API_KEY:
                    generate_sarvam_audio(dia_text, vp['voice'], vp['pace'], tmp)
                else:
                    # Fallback silent audio 1 sec if no key (to avoid crash)
                    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", "1", tmp], capture_output=True)
                temp_audios.append(tmp)
            except Exception as e:
                print(f"Audio failed {char_name}: {e}")
                continue

        if not temp_audios:
            return {"error": "Audio generation failed"}

        # 3. Concat audios using ffmpeg - NO RAM (disk only)
        with open(list_file, "w") as f:
            for tf in temp_audios:
                f.write(f"file '{tf}'\n")
        
        # Use ffmpeg concat demuxer - super lightweight
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", audio_file], check=True, capture_output=True)
        
        # Get duration
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_file], capture_output=True, text=True)
        try:
            duration = float(result.stdout.strip())
        except:
            duration = 5.0
        duration = max(5.0, duration)

        # 4. Create single background image (no moviepy)
        bg_image = create_background_image(req.channel, req.topic, 720, 1280)

        # 5. Create video using ffmpeg only - NO moviepy (saves 300MB RAM)
        # ffmpeg -loop 1 -i image -i audio -c:v libx264 -t duration -pix_fmt yuv420p -shortest
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", bg_image,
            "-i", audio_file,
            "-c:v", "libx264",
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-vf", "scale=720:1280",
            video_file
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Cleanup temp files
        try:
            os.remove(bg_image)
            os.remove(list_file)
            os.remove(audio_file)
            for tf in temp_audios:
                os.remove(tf)
        except:
            pass
        gc.collect()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Video failed: {e}"}

    return FileResponse(video_file, filename=f"{safe}.mp4", media_type="video/mp4")
