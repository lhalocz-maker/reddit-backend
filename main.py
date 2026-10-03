import os
import subprocess
import asyncio
import imageio_ffmpeg
import gdown
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import edge_tts
from PIL import Image, ImageDraw

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

DRIVE_VIDEOS = {
    "minecraft.mp4": "1Z4fdCjz7jcEt6m-aaLx1o3dc631CA81j",
    "subway.mp4": "1ceIBmGIcI077B6jbgUUMinFQYs0a8gX-",
    "gta.mp4": "1K7OyVgX6cbv5rPJbjKjgWxt9OTl6uvUg"
}

class GenerateRequest(BaseModel):
    script_text: str
    voice_id: str = "en-US-ChristopherNeural"
    bg_youtube_url: str = ""
    title_text: str = "r/AskReddit"

def ensure_video_downloaded(filename: str):
    if not os.path.exists(filename) and filename in DRIVE_VIDEOS:
        file_id = DRIVE_VIDEOS[filename]
        url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(url, filename, quiet=False)

def create_reddit_card(title: str, text: str, output_path="reddit_card.png"):
    img = Image.new('RGBA', (800, 350), color=(255, 255, 255, 240))
    draw = ImageDraw.Draw(img)
    draw.text((30, 30), title, fill=(120, 120, 120))
    short_text = text[:100] + "..." if len(text) > 100 else text
    draw.text((30, 90), short_text, fill=(0, 0, 0))
    img.save(output_path)
    return output_path

@app.get("/")
def home():
    return {"status": "ok", "message": "Backend běží!"}

@app.post("/generate-video")
async def generate_video(req: GenerateRequest):
    try:
        # 1. Zvuk z TTS
        audio_path = "tts_audio.mp3"
        communicate = edge_tts.Communicate(req.script_text, req.voice_id)
        await communicate.save(audio_path)

        # 2. Výběr videa
        bg_url = req.bg_youtube_url.lower()
        if "subway" in bg_url:
            bg_file = "subway.mp4"
        elif "gta" in bg_url:
            bg_file = "gta.mp4"
        else:
            bg_file = "minecraft.mp4"

        ensure_video_downloaded(bg_file)

        if not os.path.exists(bg_file):
            return JSONResponse({"status": "error", "message": f"Video {bg_file} nenalezeno."}, status_code=400)

        # 3. Reddit Karta
        card_img_path = create_reddit_card(req.title_text, req.script_text)

        output_filename = "final_output.mp4"
        output_path = os.path.join("static", output_filename)

        # 4. Nenáročné spojení přes FFmpeg (1 thread pro stabilitu na Free tieru)
        cmd = [
            ffmpeg_path, "-y",
            "-i", bg_file,
            "-i", audio_path,
            "-i", card_img_path,
            "-filter_complex", "[0:v][2:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:enable='between(t,0,5)'[v]",
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-threads", "1",
            "-c:a", "aac",
            "-shortest",
            output_path
        ]

        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()

        video_url = f"https://reddit-backend-n9fw.onrender.com/static/{output_filename}"

        return {
            "status": "success",
            "message": "Video vygenerováno v HD!",
            "video_url": video_url
        }
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
