import os
import imageio_ffmpeg
import gdown
from fastapi import FastAPI, BackgroundTasks
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

async def render_task(req: GenerateRequest):
    audio_clip = None
    video_clip = None
    card_clip = None
    final_video = None
    try:
        audio_path = "tts_audio.mp3"
        communicate = edge_tts.Communicate(req.script_text, req.voice_id)
        await communicate.save(audio_path)
        audio_clip = AudioFileClip(audio_path)
        
        bg_url = req.bg_youtube_url.lower()
        if "subway" in bg_url:
            bg_file = "subway.mp4"
        elif "gta" in bg_url:
            bg_file = "gta.mp4"
        else:
            bg_file = "minecraft.mp4"

        ensure_video_downloaded(bg_file)

        if not os.path.exists(bg_file):
            return

        video_clip = VideoFileClip(bg_file).subclipped(0, audio_clip.duration)
        video_clip = video_clip.resized(height=480)

        card_img_path = create_reddit_card(req.title_text, req.script_text)
        card_duration = min(4.0, audio_clip.duration)
        card_clip = (ImageClip(card_img_path)
                     .with_duration(card_duration)
                     .with_position("center"))
        
        final_video = CompositeVideoClip([video_clip, card_clip])
        final_video = final_video.with_audio(audio_clip)
        
        output_filename = "final_output.mp4"
        output_path = os.path.join("static", output_filename)
        
        # Smažeme starý výstup, abychom poznali, až bude nový hotový
        if os.path.exists(output_path):
            os.remove(output_path)

        final_video.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac",
            preset="ultrafast",
            fps=24,
            threads=1,
            logger=None
        )
    except Exception as e:
        print("Chyba při renderu:", e)
    finally:
        for clip in [audio_clip, video_clip, card_clip, final_video]:
            if clip is not None:
                try:
                    clip.close()
                except Exception:
                    pass

@app.get("/")
def home():
    return {"status": "ok", "message": "Backend běží!"}

@app.post("/generate-video")
async def generate_video(req: GenerateRequest, background_tasks: BackgroundTasks):
    # Spustí proces na pozadí, takže odpoví okamžitě bez chyby 524
    background_tasks.add_task(render_task, req)
    
    video_url = "https://reddit-backend-n9fw.onrender.com/static/final_output.mp4"
    return {
        "status": "success",
        "message": "Generování spuštěno na pozadí! Počkej cca 1–2 minuty a otevři video URL.",
        "video_url": video_url
    }
