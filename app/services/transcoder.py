import os
import subprocess
import hashlib
import signal
from pathlib import Path
from typing import AsyncGenerator

from app.config import DATA_DIR

TRANSCODE_DIR = DATA_DIR / "transcode_cache"
TRANSCODE_DIR.mkdir(exist_ok=True)


RESOLUTION_PRESETS = {
    "360p": {"width": 640, "height": 360, "bitrate": "800k"},
    "480p": {"width": 854, "height": 480, "bitrate": "1500k"},
    "720p": {"width": 1280, "height": 720, "bitrate": "3000k"},
    "1080p": {"width": 1920, "height": 1080, "bitrate": "5000k"},
}


def get_cache_key(file_path: str, resolution: str) -> str:
    h = hashlib.md5(f"{file_path}:{resolution}".encode()).hexdigest()
    return h


def get_video_streams(file_path: str) -> dict:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", "-show_format", file_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return {"audio_tracks": [], "subtitle_tracks": []}

        import json
        data = json.loads(result.stdout)
        audio_tracks = []
        subtitle_tracks = []

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                tags = stream.get("tags", {})
                audio_tracks.append({
                    "index": stream["index"],
                    "codec": stream.get("codec_name", "unknown"),
                    "language": tags.get("language", "und"),
                    "title": tags.get("title", f"Track {len(audio_tracks) + 1}"),
                    "channels": stream.get("channels", 2),
                })
            elif stream.get("codec_type") == "subtitle":
                tags = stream.get("tags", {})
                subtitle_tracks.append({
                    "index": stream["index"],
                    "codec": stream.get("codec_name", "unknown"),
                    "language": tags.get("language", "und"),
                    "title": tags.get("title", f"Subtitle {len(subtitle_tracks) + 1}"),
                })

        return {"audio_tracks": audio_tracks, "subtitle_tracks": subtitle_tracks}
    except Exception:
        return {"audio_tracks": [], "subtitle_tracks": []}


def extract_subtitle(file_path: str, stream_index: int) -> str | None:
    output_path = str(TRANSCODE_DIR / f"sub_{hashlib.md5(f'{file_path}:{stream_index}'.encode()).hexdigest()}.vtt")
    if os.path.exists(output_path):
        return output_path
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path,
                "-map", f"0:{stream_index}", "-c:s", "webvtt", output_path,
            ],
            capture_output=True, timeout=30,
        )
        if os.path.exists(output_path):
            return output_path
    except subprocess.TimeoutExpired:
        pass
    return None


async def transcode_stream(
    file_path: str,
    resolution: str = "720p",
    audio_track: int = 0,
    start_time: float = 0,
) -> AsyncGenerator[bytes, None]:
    preset = RESOLUTION_PRESETS.get(resolution, RESOLUTION_PRESETS["720p"])

    cmd = ["ffmpeg"]
    if start_time > 0:
        cmd += ["-ss", str(start_time)]
    cmd += [
        "-i", file_path,
        "-map", "0:v:0", "-map", f"0:a:{audio_track}",
        "-vf", f"scale={preset['width']}:{preset['height']}:force_original_aspect_ratio=decrease",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-b:v", preset["bitrate"], "-maxrate", preset["bitrate"],
        "-bufsize", str(int(preset["bitrate"].rstrip("k")) * 2) + "k",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-f", "mpegts",
        "-mpegts_flags", "initial_discontinuity",
        "-",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        while True:
            chunk = process.stdout.read(65536)
            if not chunk:
                break
            yield chunk
    finally:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
