import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import edge_tts
from moviepy import VideoFileClip, AudioFileClip
import yt_dlp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRequest(BaseModel):
    script_text: str
    voice_id: str = "en-US-ChristopherNeural"
    bg_youtube_url: str

@app.get("/")
def home():
    return {"status": "ok", "message": "Backend běží!"}

@app.post("/generate-video")
async def generate_video(req: GenerateRequest):
    # Generování audia z textu
    audio_path = "tts_audio.mp3"
    communicate = edge_tts.Communicate(req.script_text, req.voice_id)
    await communicate.save(audio_path)
    
    # Stažení úseku z YouTube
    raw_video = "bg_downloaded.mp4"
    if os.path.exists(raw_video):
        os.remove(raw_video)
        
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio/best[ext=mp4]/best',
        'outtmpl': raw_video,
        'external_downloader': 'ffmpeg',
        'external_downloader_args': ['-ss', '00:00:10', '-to', '00:01:10'],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([req.bg_youtube_url])
        
    # Střih a spojení
    audio_clip = AudioFileClip(audio_path)
    video_clip = VideoFileClip(raw_video).subclipped(0, audio_clip.duration)
    
    final_clip = video_clip.with_audio(audio_clip)
    output_path = "final_output.mp4"
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    audio_clip.close()
    video_clip.close()
    
    return {"status": "success", "message": "Video vygenerováno!"}
