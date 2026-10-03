import os
import imageio_ffmpeg
import gdown
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import edge_tts
from moviepy import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip
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
    img = Image.new('RGBA', (600, 250), color=(255, 255, 255, 240))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), title, fill=(120, 120, 120))
    short_text = text[:100] + "..." if len(text) > 100 else text
    draw.text((20, 60), short_text, fill=(0, 0, 0))
    img.save(output_path)
    return output_path

@app.get("/")
def home():
    return {"status": "ok", "message": "Backend běží!"}

@app.post("/generate-video")
async def generate_video(req: GenerateRequest):
    try:
        # 1. Generování zvuku z textu
        audio_path = "tts_audio.mp3"
        communicate = edge_tts.Communicate(req.script_text, req.voice_id)
        await communicate.save(audio_path)
        audio_clip = AudioFileClip(audio_path)
        
        # 2. Určení videa
        bg_url = req.bg_youtube_url.lower()
        if "subway" in bg_url:
            bg_file = "subway.mp4"
        elif "gta" in bg_url:
            bg_file = "gta.mp4"
        else:
            bg_file = "minecraft.mp4"

        ensure_video_downloaded(bg_file)

        if not os.path.exists(bg_file):
            return {"status": "error", "message": f"Video {bg_file} nenalezeno."}

        # Načtení videa a úprava rozlišení na 720p pro úsporu RAM
        video_clip = VideoFileClip(bg_file).subclipped(0, audio_clip.duration)
        video_clip = video_clip.resized(height=720)

        # 3. Reddit karta
        card_img_path = create_reddit_card(req.title_text, req.script_text)
        card_duration = min(4.0, audio_clip.duration)
        card_clip = (ImageClip(card_img_path)
                     .with_duration(card_duration)
                     .with_position("center"))
        
        # 4. Spojení a rychlý zápis
        final_video = CompositeVideoClip([video_clip, card_clip])
        final_video = final_video.with_audio(audio_clip)
        
        output_filename = "final_output.mp4"
        output_path = os.path.join("static", output_filename)
        
        # Ultrafast export pro eliminaci chyby 502/RAM
        final_video.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac",
            preset="ultrafast",
            threads=2,
            logger=None
        )
        
        audio_clip.close()
        video_clip.close()
        
        video_url = f"https://reddit-backend-n9fw.onrender.com/static/{output_filename}"
        
        return {
            "status": "success",
            "message": "Video vygenerováno!",
            "video_url": video_url
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
