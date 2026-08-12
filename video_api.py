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

app = FastAPI(title="Telugu Video Factory - ULTIMATE NATURAL v8 with Tricks")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

# ULTIMATE: Use female voices for clarity + pitch shift for male = super natural
VOICE_PROFILES = {
    "young_female": {"voice": "shruti", "pace": 1.0, "pitch_shift": 1.0, "desc": "Shruti - most clear natural"},
    "young_male": {"voice": "shruti", "pace": 1.0, "pitch_shift": 0.85, "desc": "Shruti pitched to male - natural + clear (trick)"},
    "middle_female": {"voice": "kavya", "pace": 0.98, "pitch_shift": 1.0, "desc": "Kavya natural"},
    "middle_male": {"voice": "kavya", "pace": 0.98, "pitch_shift": 0.85, "desc": "Kavya pitched to male"},
    "old_female": {"voice": "kavitha", "pace": 0.92, "pitch_shift": 1.0, "desc": "Kavitha warm"},
    "old_male": {"voice": "kavitha", "pace": 0.92, "pitch_shift": 0.80, "desc": "Kavitha pitched to old male - deep natural"},
    "kid_female": {"voice": "tanya", "pace": 1.05, "pitch_shift": 1.0},
    "kid_male": {"voice": "tanya", "pace": 1.05, "pitch_shift": 0.90},
}

class VideoRequest(BaseModel):
    channel: str
    topic: str
    voice: str = "shruti"
    id: str = "1"

def is_telugu_script(text):
    return any('\u0c00' <= c <= '\u0c7f' for c in text)

def transliterate_to_telugu(text):
    if is_telugu_script(text) or not SARVAM_API_KEY:
        return text
    if not re.search(r'[a-zA-Z]', text):
        return text
    try:
        url = "https://api.sarvam.ai/transliterate"
        headers = {"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"}
        payload = {"input": text, "source_language_code": "en-IN", "target_language_code": "te-IN"}
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            telugu = data.get("transliterated_text") or data.get("output") or ""
            if telugu and is_telugu_script(telugu):
                return telugu
    except:
        pass
    return text

def make_natural_chunks(text):
    """Break long sentence into small natural chunks - home style"""
    text = text.strip()
    # Split by commas and natural pause points
    # Telugu natural pauses: , ! ? వల్ల
    chunks = re.split(r'[,\!।\n]+', text)
    chunks = [c.strip() for c in chunks if c.strip()]
    # If no comma, split by spaces into 4-5 word chunks
    final_chunks = []
    for ch in chunks:
        words = ch.split()
        if len(words) > 6:
            # Split into 4-word groups for natural
            for i in range(0, len(words), 4):
                final_chunks.append(" ".join(words[i:i+4]))
        else:
            final_chunks.append(ch)
    return final_chunks

def detect_verified(script: str):
    fallback = {}
    names = re.findall(r'([A-Za-z\u0C00-\u0C7F]+)\s*:', script)
    for n in names:
        orig_n = n.strip()
        n_low = orig_n.lower()
        if any(k in orig_n for k in ["అమ్మ", "అవ్వ", "బామ్మ", "అమ్మమ్మ", "అత్త"]) or any(k in n_low for k in ["amma","avva","ammamma"]):
            fallback[orig_n] = {"gender":"female","age_group":"old"}
            continue
        if any(k in orig_n for k in ["తాత", "నాన్న", "అయ్య", "తాతయ్య"]) or any(k in n_low for k in ["thatha","nanna","tata"]):
            fallback[orig_n] = {"gender":"male","age_group":"old"}
            continue
        if any(k in orig_n for k in ["చిన్న", "పాప", "బాబు","చింటు","చింటూ"]) or any(k in n_low for k in ["chinna","papa","babu"]):
            if orig_n.endswith('ా') or n_low.endswith('a'):
                fallback[orig_n] = {"gender":"female","age_group":"kid"}
            else:
                fallback[orig_n] = {"gender":"male","age_group":"kid"}
            continue
        if orig_n.endswith('ా') or n_low.endswith('a') or any(k in orig_n for k in ["సీత","గీత","ప్రియ","కావ్య"]):
            fallback[orig_n] = {"gender":"female","age_group":"young"}
            continue
        fallback[orig_n] = {"gender":"male","age_group":"young"}
    return fallback

def get_voice_verified(gender, age_group):
    if gender == "female":
        if age_group == "old": return VOICE_PROFILES["old_female"]
        if age_group == "kid": return VOICE_PROFILES["kid_female"]
        if age_group == "middle": return VOICE_PROFILES["middle_female"]
        return VOICE_PROFILES["young_female"]
    else:
        if age_group == "old": return VOICE_PROFILES["old_male"]
        if age_group == "kid": return VOICE_PROFILES["kid_male"]
        if age_group == "middle": return VOICE_PROFILES["middle_male"]
        return VOICE_PROFILES["young_male"]

def generate_and_enhance(text, voice_name, pace, pitch_shift, audio_file):
    """Generate + Enhance for natural + pitch shift for male"""
    if not SARVAM_API_KEY:
        raise Exception("SARVAM_API_KEY missing")
    
    telugu_text = transliterate_to_telugu(text) if not is_telugu_script(text) else text
    
    url = "https://api.sarvam.ai/text-to-speech"
    headers = {"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"}
    payload = {
        "inputs": [telugu_text],
        "target_language_code": "te-IN",
        "speaker": voice_name.lower(),
        "pace": pace,
        "model": "bulbul:v3"
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"Sarvam Error: {r.text[:300]}")
    r.raise_for_status()
    data = r.json()
    tmp_raw = audio_file.replace(".wav", "_raw.wav")
    with open(tmp_raw, "wb") as f:
        f.write(base64.b64decode(data["audios"][0]))
    
    # TRICK: Pitch shift for male voices + enhance for natural
    if pitch_shift != 1.0:
        # Female voice -> Male pitch: lower pitch, keep clarity
        # asetrate trick: 0.85 = 15% deeper = natural male
        cmd = [
            "ffmpeg", "-y", "-i", tmp_raw,
            "-af", f"asetrate=22050*{pitch_shift},aresample=22050,highpass=f=80,lowpass=f=8000,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "pcm_s16le",
            audio_file
        ]
    else:
        # Female natural enhance only
        cmd = [
            "ffmpeg", "-y", "-i", tmp_raw,
            "-af", "highpass=f=80,lowpass=f=8000,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "pcm_s16le",
            audio_file
        ]
    subprocess.run(cmd, check=True, capture_output=True)
    try:
        os.remove(tmp_raw)
    except:
        pass
    return True

def create_bg(channel, topic, w=720, h=1280):
    img = Image.new('RGB', (w, h), (15, 23, 42))
    draw = ImageDraw.Draw(img)
    try:
        f1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        f2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        f1 = ImageFont.load_default(); f2 = ImageFont.load_default()
    draw.text((w//2, 120), channel[:30], font=f1, fill=(255,221,0), anchor="mm")
    y=300
    for line in topic.split('\n')[:6]:
        if ':' in line:
            name,dia=line.split(':',1)
            col=(100,200,255) if any(k in name for k in ["అమ్మ","amma"]) else (255,180,100)
            draw.text((w//2,y), f"{name.strip()}:", font=f2, fill=col, anchor="mm"); y+=35
            draw.text((w//2,y), dia.strip()[:65], font=f2, fill=(255,255,255), anchor="mm"); y+=50
        y+=15
    p=f"/tmp/bg_{uuid.uuid4().hex[:6]}.png"; img.save(p); return p

@app.get("/")
def home():
    return {"status":"ULTIMATE v8 - Pitch Shift Trick for Natural Male"}

@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/generate")
async def generate_video(req: VideoRequest):
    safe="".join([c for c in req.channel if c.isalnum() or c in "_-"])[:20]
    uid=uuid.uuid4().hex[:6]
    audio_file=f"/tmp/{safe}_{uid}_final.mp3"
    video_file=f"/tmp/{safe}_{uid}.mp4"
    list_file=f"/tmp/{safe}_{uid}_list.txt"
    temp_audios=[]
    try:
        detected=detect_verified(req.topic)
        dialogues=[]
        for line in req.topic.split('\n'):
            line=line.strip()
            if not line: continue
            if ':' in line and len(line.split(':')[0])<30:
                name,dia=line.split(':',1)
                name=name.strip()
                info=detected.get(name, {"gender":"female" if name.endswith('ా') or name.lower().endswith('a') else "male","age_group":"young"})
                vp=get_voice_verified(info['gender'], info['age_group'])
                # Break dialogue into natural chunks
                chunks=make_natural_chunks(dia.strip())
                for ch in chunks:
                    dialogues.append((name,ch,vp))
            else:
                vp=VOICE_PROFILES["young_female"]
                chunks=make_natural_chunks(line)
                for ch in chunks:
                    dialogues.append(("Narrator",ch,vp))

        for idx,(char_name,dia_text,vp) in enumerate(dialogues):
            tmp=f"/tmp/{safe}_{uid}_{idx}.wav"
            print(f"[{idx+1}] {char_name} -> {vp['voice']} pitch={vp['pitch_shift']} pace={vp['pace']} : {dia_text}")
            try:
                generate_and_enhance(dia_text, vp['voice'], vp['pace'], vp['pitch_shift'], tmp)
                temp_audios.append(tmp)
                # Natural pause 0.35 sec
                sil=f"/tmp/{safe}_{uid}_{idx}_sil.wav"
                subprocess.run(["ffmpeg","-y","-f","lavfi","-i","anullsrc=r=22050:cl=mono","-t","0.35","-c:a","pcm_s16le",sil], capture_output=True)
                if os.path.exists(sil):
                    temp_audios.append(sil)
            except Exception as e:
                print(f"Fail {char_name}: {e}")
                continue

        if not temp_audios:
            return {"error":"Audio failed"}

        with open(list_file,"w") as f:
            for tf in temp_audios:
                f.write(f"file '{tf}'\n")
        subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",list_file,"-c:a","libmp3lame","-b:a","128k",audio_file], check=True, capture_output=True)

        result=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",audio_file], capture_output=True, text=True)
        try:
            duration=float(result.stdout.strip())
        except:
            duration=5.0
        duration=max(5.0,duration)
        bg=create_bg(req.channel, req.topic)
        cmd=["ffmpeg","-y","-loop","1","-i",bg,"-i",audio_file,"-c:v","libx264","-t",str(duration),"-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-shortest","-vf","scale=720:1280",video_file]
        subprocess.run(cmd, check=True, capture_output=True)
        try:
            os.remove(bg); os.remove(list_file); os.remove(audio_file)
            for tf in temp_audios:
                if os.path.exists(tf): os.remove(tf)
        except:
            pass
        gc.collect()
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error":f"Video failed: {e}"}
    return FileResponse(video_file, filename=f"{safe}.mp4", media_type="video/mp4")
