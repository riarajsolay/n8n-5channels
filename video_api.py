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
import time
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Telugu Video Factory - Natural Voice v5")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

# NATURAL VOICES - Tested best for Telugu
VOICE_PROFILES = {
    "young_female": {"voice": "shruti", "pace": 1.0},    # most natural young girl
    "young_male": {"voice": "amit", "pace": 1.0},        # natural young boy
    "middle_female": {"voice": "kavya", "pace": 0.95},
    "middle_male": {"voice": "rohan", "pace": 0.95},
    "old_female": {"voice": "kavitha", "pace": 0.80},    # slow + warm for ammamma
    "old_male": {"voice": "anand", "pace": 0.80},        # slow + deep for thathayya
    "kid_female": {"voice": "tanya", "pace": 1.10},
    "kid_male": {"voice": "aayan", "pace": 1.10},
}

class VideoRequest(BaseModel):
    channel: str
    topic: str
    voice: str = "shruti"
    id: str = "1"

def is_telugu_script(text):
    return any('\u0c00' <= c <= '\u0c7f' for c in text)

def transliterate_to_telugu(text):
    """Roman Telugu -> Telugu script for natural voice - FREE"""
    if is_telugu_script(text) or not SARVAM_API_KEY:
        return text
    # Only transliterate if English letters
    if not re.search(r'[a-zA-Z]', text):
        return text
    try:
        url = "https://api.sarvam.ai/transliterate"
        headers = {"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"}
        payload = {
            "input": text,
            "source_language_code": "en-IN",
            "target_language_code": "te-IN"
        }
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # response may have transliterated_text
            telugu = data.get("transliterated_text") or data.get("output") or ""
            if telugu and is_telugu_script(telugu):
                print(f"Transliterated: {text} -> {telugu}")
                return telugu
    except Exception as e:
        print(f"Transliteration failed: {e}")
    return text

def make_natural_text(text):
    """Add natural punctuation and emotion"""
    text = text.strip()
    # Remove character name if included in dialogue part
    # Add natural Telugu punctuation
    if not text.endswith(('!', '?', '।', '.', ',')):
        # Add exclamation for emotion based on keywords
        if any(w in text.lower() for w in ['ha', 'are', 'amma', 'ayyo']):
            text = text + "!"
        else:
            text = text + "."
    # Add small pause markers - replace : with ,
    text = text.replace(":", ",")
    # Make it more expressive - add space after comma
    text = re.sub(r',\s*', ', ', text)
    return text

def detect_characters_fast(script: str):
    fallback = {}
    names = re.findall(r'([A-Za-z\u0C00-\u0C7F]+)\s*:', script)
    for n in names:
        n = n.strip()
        n_low = n.lower()
        if any(x in n_low for x in ['amma','avva','bomma','mother','kavitha']): fallback[n] = {"gender":"female","age_group":"old"}
        elif any(x in n_low for x in ['thatha','nanna','father','tata','anand','gokul']): fallback[n] = {"gender":"male","age_group":"old"}
        elif any(x in n_low for x in ['chinna','chintu','pilla','babu','pappu','kid','aayan','tanya']): 
            if n_low.endswith('a') or 'tanya' in n_low: fallback[n] = {"gender":"female","age_group":"kid"}
            else: fallback[n] = {"gender":"male","age_group":"kid"}
        elif n_low.endswith('a') or n_low in ['priya','kavya','shruti','sita','geeta','roopa','tanya']: fallback[n] = {"gender":"female","age_group":"young"}
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
    if not SARVAM_API_KEY:
        raise Exception("SARVAM_API_KEY missing")
    # 1. Make text natural + transliterate
    natural = make_natural_text(text)
    telugu_text = transliterate_to_telugu(natural)
    
    url = "https://api.sarvam.ai/text-to-speech"
    headers = {"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"}
    payload = {
        "inputs": [telugu_text],
        "target_language_code": "te-IN",
        "speaker": voice_name.lower(),
        "pace": pace,
        "model": "bulbul:v3"
    }
    print(f"Sarvam: {voice_name} ({pace}) -> {telugu_text}")
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"Sarvam ERROR {r.status_code}: {r.text[:300]}")
    r.raise_for_status()
    data = r.json()
    audio_b64 = data["audios"][0]
    with open(audio_file, "wb") as f:
        f.write(base64.b64decode(audio_b64))
    return True

def create_background_image(channel, topic, width=720, height=1280):
    img = Image.new('RGB', (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(img)
    try:
        font_channel = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
        font_topic = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    except:
        font_channel = ImageFont.load_default()
        font_topic = ImageFont.load_default()
    draw.text((width//2, 150), channel[:30], font=font_channel, fill=(255,221,0), anchor="mm")
    # Show dialogues nicely
    y = 350
    for line in topic.split('\n')[:6]:
        if ':' in line:
            name, dia = line.split(':',1)
            draw.text((width//2, y), f"{name.strip()}:", font=font_topic, fill=(100,200,255), anchor="mm")
            y+=40
            # wrap dialogue
            words = dia.strip()[:60].split()
            l = ""
            for w in words:
                if len(l+w) > 30:
                    draw.text((width//2, y), l, font=font_topic, fill=(255,255,255), anchor="mm")
                    y+=40
                    l=w+" "
                else:
                    l+=w+" "
            if l:
                draw.text((width//2, y), l, font=font_topic, fill=(255,255,255), anchor="mm")
                y+=50
        else:
            draw.text((width//2, y), line[:50], font=font_topic, fill=(255,255,255), anchor="mm")
            y+=45
        y+=20
        if y>1000: break
    
    path = f"/tmp/bg_{uuid.uuid4().hex[:6]}.png"
    img.save(path)
    return path

@app.get("/")
def home():
    return {"status": "OK - Natural v5", "natural": "Telugu script + emotion + pace"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate")
async def generate_video(req: VideoRequest):
    safe = "".join([c for c in req.channel if c.isalnum() or c in "_-"])[:20]
    uid = uuid.uuid4().hex[:6]
    audio_file = f"/tmp/{safe}_{uid}_final.mp3"
    video_file = f"/tmp/{safe}_{uid}.mp4"
    list_file = f"/tmp/{safe}_{uid}_list.txt"
    
    print(f"Generating NATURAL: {req.channel} - {req.topic[:60]}")
    temp_audios = []
    
    try:
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

        for idx, (char_name, dia_text, vp) in enumerate(dialogues):
            tmp = f"/tmp/{safe}_{uid}_{idx}.wav"
            print(f"Audio {idx+1}/{len(dialogues)} for {char_name} ({vp['voice']} pace={vp['pace']})")
            try:
                generate_sarvam_audio(dia_text, vp['voice'], vp['pace'], tmp)
                temp_audios.append(tmp)
                # Small natural pause between characters - 0.3 sec silence
                silence = f"/tmp/{safe}_{uid}_{idx}_sil.wav"
                subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", "0.3", "-c:a", "pcm_s16le", silence], capture_output=True)
                if os.path.exists(silence):
                    temp_audios.append(silence)
            except Exception as e:
                print(f"Audio failed {char_name}: {e}")
                continue

        if not temp_audios:
            return {"error": "Audio generation failed"}

        with open(list_file, "w") as f:
            for tf in temp_audios:
                f.write(f"file '{tf}'\n")
        
        concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c:a", "libmp3lame", "-b:a", "128k", audio_file]
        result = subprocess.run(concat_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Concat failed: {result.stderr}")
            inputs = []
            for tf in temp_audios:
                inputs.extend(["-i", tf])
            filter_complex = "".join([f"[{i}:a]" for i in range(len(temp_audios))]) + f"concat=n={len(temp_audios)}:v=0:a=1[a]"
            fallback_cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_complex, "-map", "[a]", "-c:a", "libmp3lame", audio_file]
            subprocess.run(fallback_cmd, check=True, capture_output=True)
        
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_file], capture_output=True, text=True)
        try:
            duration = float(result.stdout.strip())
        except:
            duration = 5.0
        duration = max(5.0, duration)

        bg_image = create_background_image(req.channel, req.topic, 720, 1280)

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
        
        try:
            os.remove(bg_image)
            os.remove(list_file)
            os.remove(audio_file)
            for tf in temp_audios:
                if os.path.exists(tf):
                    os.remove(tf)
        except:
            pass
        gc.collect()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Video failed: {e}"}

    return FileResponse(video_file, filename=f"{safe}.mp4", media_type="video/mp4")
