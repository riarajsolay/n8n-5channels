from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid
import os
import re
import subprocess
import gc
import asyncio
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Telugu Video Factory - EDGE TTS FREE NATURAL")

# EDGE TTS - 100% FREE, Most Natural Telugu - No API Key Needed!
# Voices: te-IN-MohanNeural (male natural), te-IN-ShrutiNeural (female natural)
# This is what Korean dubbing channels use!

EDGE_VOICES = {
    "young_female": {"voice": "te-IN-ShrutiNeural", "desc": "Shruti - super natural young girl FREE"},
    "young_male": {"voice": "te-IN-MohanNeural", "desc": "Mohan - super natural young boy FREE"},
    "middle_female": {"voice": "te-IN-ShrutiNeural", "desc": "Shruti middle"},
    "middle_male": {"voice": "te-IN-MohanNeural", "desc": "Mohan middle"},
    "old_female": {"voice": "te-IN-ShrutiNeural", "rate": "-10%", "desc": "Shruti slow for ammamma"},
    "old_male": {"voice": "te-IN-MohanNeural", "rate": "-10%", "desc": "Mohan slow for thathayya"},
    "kid_female": {"voice": "te-IN-ShrutiNeural", "rate": "+10%", "desc": "Shruti fast for papa"},
    "kid_male": {"voice": "te-IN-MohanNeural", "rate": "+10%", "desc": "Mohan fast for babu"},
}

class VideoRequest(BaseModel):
    channel: str
    topic: str
    voice: str = "te-IN-ShrutiNeural"
    id: str = "1"

def detect_verified(script: str):
    fallback = {}
    names = re.findall(r'([A-Za-z\u0C00-\u0C7F]+)\s*:', script)
    for n in names:
        orig_n = n.strip()
        n_low = orig_n.lower()
        if any(k in orig_n for k in ["అమ్మ", "అవ్వ", "బామ్మ", "అమ్మమ్మ"]) or any(k in n_low for k in ["amma","avva","ammamma"]):
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
        if orig_n.endswith('ా') or n_low.endswith('a'):
            fallback[orig_n] = {"gender":"female","age_group":"young"}
            continue
        fallback[orig_n] = {"gender":"male","age_group":"young"}
    print(f"Detection: {fallback}")
    return fallback

def get_voice_verified(gender, age_group):
    if gender == "female":
        if age_group == "old": return EDGE_VOICES["old_female"]
        if age_group == "kid": return EDGE_VOICES["kid_female"]
        if age_group == "middle": return EDGE_VOICES["middle_female"]
        return EDGE_VOICES["young_female"]
    else:
        if age_group == "old": return EDGE_VOICES["old_male"]
        if age_group == "kid": return EDGE_VOICES["kid_male"]
        if age_group == "middle": return EDGE_VOICES["middle_male"]
        return EDGE_VOICES["young_male"]

async def generate_edge_tts(text, voice, rate, audio_file):
    """Edge TTS - FREE, Natural, No API Key"""
    import edge_tts
    # Make natural - add punctuation if missing
    text = text.strip()
    if text and text[-1] not in ('!', '?', '.', ',', '।'):
        text = text + "."
    
    print(f"Edge TTS: {voice} rate={rate} -> {text}")
    communicate = edge_tts.Communicate(text, voice, rate=rate if rate else "+0%")
    await communicate.save(audio_file)
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
    return {"status":"EDGE TTS FREE NATURAL - Like Korean Dubbing Channels", "cost":"100% FREE", "voices":"te-IN-MohanNeural, te-IN-ShrutiNeural"}

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
                dialogues.append((name,dia.strip(),vp))
            else:
                vp=EDGE_VOICES["young_female"]
                dialogues.append(("Narrator",line,vp))

        for idx,(char_name,dia_text,vp) in enumerate(dialogues):
            tmp=f"/tmp/{safe}_{uid}_{idx}.mp3"
            print(f"[{idx+1}] {char_name} -> {vp['voice']} : {dia_text}")
            try:
                rate = vp.get("rate", "+0%")
                await generate_edge_tts(dia_text, vp['voice'], rate, tmp)
                temp_audios.append(tmp)
                sil=f"/tmp/{safe}_{uid}_{idx}_sil.mp3"
                subprocess.run(["ffmpeg","-y","-f","lavfi","-i","anullsrc=r=22050:cl=mono","-t","0.35","-c:a","libmp3lame",sil], capture_output=True)
                if os.path.exists(sil):
                    temp_audios.append(sil)
            except Exception as e:
                print(f"Fail {char_name}: {e}")
                import traceback; traceback.print_exc()
                continue

        if not temp_audios:
            return {"error":"Audio failed - Edge TTS"}

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
