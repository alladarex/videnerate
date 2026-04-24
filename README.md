# Videnerate

A desktop app for creating short-form videos from a single
idea, narration, or audio file. Built with Python and PySide6 (Qt).

Videnerate turns text into narrated, segment-by-segment video: it
generates or imports narration, splits it into short lines, lets you
pick an image, video, or GIF for each line from Google (DuckDuckGO), Pexels, Pixabay, 
and Giphy, and exports the result as an MP4 using FFmpeg.

## Features

- Narration from an AI prompt, your own text, or an uploaded audio file
- Voiceover via Google TTS or ElevenLabs, with optional silence removal
- Grid-based segment editor (5–13 word lines)
- Media search across Google, Pexels, Pixabay, and Giphy
- Auto-Fill: one keyword + one clip per segment, automatically (WIP)
- Local MP4 export with vertical framing, blur backgrounds, and image zoom (WIP)
- Projects stored as plain folders on disk — no database, no cloud

## Setup

- Python 3.12
- [FFmpeg](https://ffmpeg.org/download.html) on your PATH
- API keys for whatever services you plan to use (see `.env.example`)

You don't need every key for media search (Pexels, Pixabay, Giphy). A Google/DuckDuckGo search can be used. ChatGPT and ElevenLabs API not used currently.

## Running it locally

Clone and enter the project:

```bash
git clone https://github.com/alladarex/videnerate.git
cd videnerate
```

Set up a virtualenv. On Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

On macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the deps and copy the env file:

```bash
pip install -r requirements.txt
cp .env.example .env
```

Open `.env`, paste in your API keys, then start the app:

```bash
python main.py
```

The start window will open. Pick "Enter video idea"and go from there. "Enter narration",
or "Upload audio file" are not implemented yet.

## Running it with Docker

It's a Qt desktop app, so the container needs to draw to your host
display. The image also ships with a sample project in
`projects/example/` so you can load a project without setting one up
yourself.

Build:

```bash
docker build -t videnerate .
```

Make sure `.env` exists in the project root before you run. Then, on
Linux:

```bash
xhost +local:docker

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$(pwd)/projects:/videnerate/projects" \
  --env-file .env \
  videnerate
```

The `--user` bit just makes sure any files the app writes into
`projects/` end up owned by you, not root. Skip it if you don't care.

On Windows or macOS you'll need an X server running on the host
([VcXsrv](https://sourceforge.net/projects/vcxsrv/) for Windows,
[XQuartz](https://www.xquartz.org/) for macOS), then:

```bash
docker run --rm \
  -e DISPLAY=host.docker.internal:0 \
  -v "$(pwd)/projects:/videnerate/projects" \
  --env-file .env \
  videnerate
```

Projects are written to the mounted `projects/` folder on your
machine, so nothing is lost when the container exits.

## Repo layout

```text
main.py            entry point
ui/                PySide6 windows and widgets
services/          API wrappers (Pexels, Pixabay, Giphy, TTS, ...)
core/              narration, audio, and video processing
projects/          one folder per video project
requirements.txt
Dockerfile
.env.example
```

Every project is just a folder with a `project.json`, a
`narration.txt`, and `media/` and `audio/` subfolders. Zip one up and
you can move it anywhere.