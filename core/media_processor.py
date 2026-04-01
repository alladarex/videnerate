import os
import requests
import ffmpeg
from pathlib import Path
from typing import List, Dict, Union
from config import PEXELS_API_KEY, PIXABAY_API_KEY, TEMP_DIR

def search_media(keyword: str, media_type: str = "all") -> List[Dict[str, str]]:
    """
    Search for media (images/videos) using the given keyword.
    Returns a list of media items with their metadata.
    """
    results = []
    
    # Search Pexels
    if PEXELS_API_KEY:
        headers = {"Authorization": PEXELS_API_KEY}
        
        # Search photos
        if media_type in ["all", "photo"]:
            response = requests.get(
                f"https://api.pexels.com/v1/search?query={keyword}&orientation=portrait&per_page=5",
                headers=headers
            )
            if response.status_code == 200:
                photos = response.json().get("photos", [])
                for photo in photos:
                    results.append({
                        "type": "image",
                        "source": "pexels",
                        "url": photo["src"]["portrait"],
                        "thumbnail": photo["src"]["medium"],
                        "width": photo["width"],
                        "height": photo["height"],
                    })
        
        # Search videos
        if media_type in ["all", "video"]:
            response = requests.get(
                f"https://api.pexels.com/videos/search?query={keyword}&orientation=portrait&per_page=5",
                headers=headers
            )
            if response.status_code == 200:
                videos = response.json().get("videos", [])
                for video in videos:
                    # Find HD or SD video file
                    video_file = next(
                        (f for f in video["video_files"] 
                         if f["quality"] in ["hd", "sd"] and f["width"] < f["height"]),
                        None
                    )
                    if video_file:
                        results.append({
                            "type": "video",
                            "source": "pexels",
                            "url": video_file["link"],
                            "thumbnail": video["image"],
                            "width": video_file["width"],
                            "height": video_file["height"],
                            "duration": video["duration"],
                        })
    
    # Search Pixabay
    if PIXABAY_API_KEY:
        # Search images
        if media_type in ["all", "photo"]:
            response = requests.get(
                f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={keyword}&orientation=vertical&per_page=5"
            )
            if response.status_code == 200:
                images = response.json().get("hits", [])
                for image in images:
                    results.append({
                        "type": "image",
                        "source": "pixabay",
                        "url": image["largeImageURL"],
                        "thumbnail": image["previewURL"],
                        "width": image["imageWidth"],
                        "height": image["imageHeight"],
                    })
        
        # Search videos
        if media_type in ["all", "video"]:
            response = requests.get(
                f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={keyword}&per_page=5"
            )
            if response.status_code == 200:
                videos = response.json().get("hits", [])
                for video in videos:
                    # Find large or medium video file
                    video_file = video.get("videos", {}).get("large", {}) or video.get("videos", {}).get("medium", {})
                    if video_file:
                        results.append({
                            "type": "video",
                            "source": "pixabay",
                            "url": video_file["url"],
                            "thumbnail": video["userImageURL"],
                            "width": video_file.get("width", 0),
                            "height": video_file.get("height", 0),
                            "duration": video.get("duration", 0),
                        })
    
    return results

def download_media(url: str, filename: str) -> str:
    """Download media from URL and return local path."""
    output_path = os.path.join(TEMP_DIR, filename)
    response = requests.get(url)
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path
    return None

def create_video(segments: List[Dict], media_items: List[Dict]) -> str:
    """
    Create final video from segments and media items.
    Each segment should have: text, audio_path, duration
    Each media_item should have: type (image/video), path
    """
    output_path = os.path.join(TEMP_DIR, "output.mp4")
    temp_segments = []
    
    # Process each segment
    for i, (segment, media) in enumerate(zip(segments, media_items)):
        # Download media if needed
        if "path" not in media:
            filename = f"media_{i}{'.mp4' if media['type'] == 'video' else '.jpg'}"
            media["path"] = download_media(media["url"], filename)
        
        # Process media based on type
        if media["type"] == "image":
            # Create video from image with zoom effect
            temp_path = os.path.join(TEMP_DIR, f"temp_{i}.mp4")
            stream = ffmpeg.input(media["path"], loop=1, t=segment["duration"])
            
            # Apply zoom effect
            stream = ffmpeg.filter(stream, "scale", w="iw*1.5", h="ih*1.5")
            stream = ffmpeg.filter(stream, "crop", w="iw/1.5", h="ih/1.5")
            
            # Add background blur if vertical
            if media["height"] > media["width"]:
                bg = ffmpeg.filter(stream, "scale", w=1080, h=1920)
                bg = ffmpeg.filter(bg, "boxblur", luma_radius=50, luma_power=1)
                fg = ffmpeg.filter(stream, "scale", w=-1, h=1920)
                stream = ffmpeg.overlay(bg, fg, x="(W-w)/2")
            
            stream = ffmpeg.output(stream, temp_path, acodec="aac", vcodec="libx264")
            ffmpeg.run(stream, overwrite_output=True)
            temp_segments.append(temp_path)
        
        else:  # video
            # Trim video if needed
            temp_path = os.path.join(TEMP_DIR, f"temp_{i}.mp4")
            stream = ffmpeg.input(media["path"])
            
            # Add background blur if vertical
            if media["height"] > media["width"]:
                bg = ffmpeg.filter(stream, "scale", w=1080, h=1920)
                bg = ffmpeg.filter(bg, "boxblur", luma_radius=50, luma_power=1)
                fg = ffmpeg.filter(stream, "scale", w=-1, h=1920)
                stream = ffmpeg.overlay(bg, fg, x="(W-w)/2")
            
            stream = ffmpeg.output(stream, temp_path, t=segment["duration"], 
                                 acodec="aac", vcodec="libx264")
            ffmpeg.run(stream, overwrite_output=True)
            temp_segments.append(temp_path)
    
    # Concatenate all segments
    concat_list = os.path.join(TEMP_DIR, "concat.txt")
    with open(concat_list, "w") as f:
        for path in temp_segments:
            f.write(f"file '{path}'\n")
    
    # Add audio
    audio_path = os.path.join(TEMP_DIR, "voice.mp3")
    stream = ffmpeg.input("concat:" + "|".join(temp_segments))
    audio = ffmpeg.input(audio_path)
    stream = ffmpeg.output(stream, audio, output_path, acodec="aac", vcodec="libx264")
    ffmpeg.run(stream, overwrite_output=True)
    
    # Clean up temp files
    for path in temp_segments:
        os.remove(path)
    os.remove(concat_list)
    
    return output_path
