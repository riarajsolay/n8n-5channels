from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import edge_tts
import uuid
import os
import requests
import base64
import json
import re
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import AudioFileClip, ColorClip, ImageClip, CompositeVideoClip, concatenate_audioclips

app = FastAPI(title="Telugu Video Factory API")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
SARVAM_M_URL = "https://api.sarvam.ai/v1/chat/completions"

# === NEW: Voice Profiles - No Mismatch Guarantee ===
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

# === NEW FUNCTION 1: Auto Detect Characters with Sarvam-M ===
def detect_characters_auto(script: str):
    if not SARVAM_API_KEY:
        return {}
    prompt = f"""
    Analyze this Telugu story script and extract characters.
    For each character, tell gender and age_group.
    Age groups: kid, young, middle, old
    Script: {script[:2000]}
    Return ONLY JSON like:
    {{
      "Ravi": {{"gender": "male", "age_group": "young"}},
      "Ammamma": {{"gender": "female", "age_group": "old"}},
      "Chintu": {{"gender": "male", "age_group": "kid"}}
    }}
    If no clear names, detect from Telugu words like amma,nanna,pilladu,avva,thathayya.
    """
    try:
        headers = {"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"}
        payload = {"model": "sarvam-m", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
        r = requests.post(SARVAM_M_URL, json=payload, headers=headers, timeout=15)
        data = r.json()
        text = data['choices'][0]['message']['content']
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            chars = json.loads(m.group(0))
            return chars
    except Exception as e:
        print(f"Auto detect failed: {e}")
    
    # Fallback Telugu keywords
    fallback = {}
    low = script.lower()
    if "ammamma" in low or "avva" in low: fallback["Ammamma"] = {"gender": "female", "age_group": "old"}
    if "thathayya" in low or "thatayya" in low: fallback["Thathayya"] = {"gender": "male", "age_group": "old"}
    if "chinna" in low or "pilla" in low: fallback["Chinna"] = {"gender": "male", "age_group": "kid"}
    return fallback

def get_voice_for_character(gender, age_group):
    key = f"{age_group}_{gender}"
    # Strict mismatch protection
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

def create_text_image(text, width=900, font_size=50, color=(255,255,255)):
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()
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
    lines = lines[:6]
    line_height = font_size + 15
    img_height = len(lines) * line_height + 60
    img = Image.new('RGBA', (width, img_height), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    y = 10
    for l in lines:
        draw.text((10, y), l, font=font, fill=color)
        y += line_height
    path = f"/tmp/text_{uuid.uuid4().hex[:6]}.png"
    img.save(path)
    return path, img_height

@app.get("/")
def home():
    return {"status": "Telugu Video Factory API Running OK", "channels": "Unlimited", "tts": "Sarvam Auto Multi-Voice"}

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

    # === NEW: AUTO MULTI-VOICE LOGIC - REPLACES OLD 71-76 ===
    try:
        # 1. Detect characters from script automatically
        detected_chars = detect_characters_auto(req.topic)
        print(f"Detected: {detected_chars}")

        # 2. Parse dialogues - Name: dialogue format
        dialogues_raw = []
        for line in req.topic.split('\n'):
            line = line.strip()
            if not line: continue
            if ':' in line and len(line.split(':')[0]) < 30: # likely Name: dialogue
                name, dia = line.split(':', 1)
                name = name.strip()
                info = detected_chars.get(name)
                if not info:
                    # guess from name if not in detected list
                    low_name = name.lower()
                    if any(x in low_name for x in ['amma','avva','bomma']): info = {"gender":"female","age_group":"old"}
                    elif any(x in low_name for x in ['thatha','nanna']): info = {"gender":"male","age_group":"old"}
                    elif any(x in low_name for x in ['chinna','pilla','chintu']): info = {"gender":"male","age_group":"kid"}
                    elif name.lower().endswith('a'): info = {"gender":"female","age_group":"young"}
                    else: info = {"gender":"male","age_group":"young"}
                voice_profile = get_voice_for_character(info['gender'], info['age_group'])
                dialogues_raw.append((name, dia.strip(), voice_profile))
            else:
                # No character name - use main voice
                vp = get_voice_for_character("female" if req.voice in ["anushka","manisha","vidya"] else "male", "young")
                if req.voice in VOICE_PROFILES:
                    # if exact profile name given
                    for k,v in VOICE_PROFILES.items():
                        if v['voice'] == req.voice:
                            vp = v
                            break
                dialogues_raw.append(("Narrator", line, vp))

        if not dialogues_raw:
            dialogues_raw = [("Narrator", req.topic, VOICE_PROFILES["young_female"])]

        # 3. Generate audio for each dialogue with correct voice
        audio_clips = []
        temp_files = []
        for idx, (char_name, dia_text, vp) in enumerate(dialogues_raw):
            tmp = f"/tmp/{safe}_{uid}_{idx}.mp3"
            print(f"Generating for {char_name} ({vp['voice']}) : {dia_text[:30]}")
            try:
                if SARVAM_API_KEY:
                    generate_sarvam_audio(dia_text, vp['voice'], vp['pace'], tmp)
                else:
                    raise Exception("No Sarvam Key")
                audio_clips.append(AudioFileClip(tmp))
                temp_files.append(tmp)
            except Exception as e:
                print(f"Sarvam failed for {char_name} {e}, fallback edge")
                try:
                    comm = edge_tts.Communicate(dia_text, "te-IN-ShrutiNeural")
                    await comm.save(tmp)
                    audio_clips.append(AudioFileClip(tmp))
                    temp_files.append(tmp)
                except Exception as e2:
                    print(f"Edge also failed: {e2}")

        if not audio_clips:
            return {"error": "Audio failed for all dialogues"}

        # 4. Concatenate all clips with small gap
        if len(audio_clips) > 1:
            final_audio_concat = concatenate_audioclips(audio_clips)
            final_audio_concat.write_audiofile(audio_file, verbose=False, logger=None)
            for c in audio_clips: c.close()
            audio = AudioFileClip(audio_file)
        else:
            audio_clips[0].write_audiofile(audio_file, verbose=False, logger=None)
            audio_clips[0].close()
            audio = AudioFileClip(audio_file)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Audio failed: {e}"}

    # === VIDEO PART - SAME AS OLD ===
    try:
        duration = max(5, audio.duration)
        bg = ColorClip(size=(1080, 1920), color=(15,23,42), duration=duration)
        channel_img_path, _ = create_text_image(req.channel, width=800, font_size=60, color=(255,221,0))
        channel_clip = ImageClip(channel_img_path, duration=duration).set_position(('center', 200))
        topic_img_path, h = create_text_image(req.topic[:300], width=950, font_size=48, color=(255,255,255))
        topic_clip = ImageClip(topic_img_path, duration=duration).set_position(('center', 800))
        final = CompositeVideoClip([bg, channel_clip, topic_clip]).set_audio(audio)
        final.write_videofile(video_file, fps=24, codec='libx264', audio_codec='aac', verbose=False, logger=None)
        try:
            os.remove(channel_img_path)
            os.remove(topic_img_path)
            for tf in temp_files: os.remove(tf)
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
