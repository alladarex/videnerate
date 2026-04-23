# Videnerate

A simple, single-page web app designed to help users create short-form videos effortlessly.

## Features

- Generate video narration from text or prompts using DeepSeek
- Convert text to speech using Google TTS or ElevenLabs
- Split narration into digestible segments
- Auto-generate keywords for visual content search
- Search and select images/videos/GIFs from Google, Giphy, Pexels, and Pixabay
- Export final video with synchronized narration and visuals

## Setup

1. Clone the repository:
git clone https://github.com/alladarex/videnerate.git
cd videnerate

2. Create and activate virtual environment:
python -m venv .venv
.venv\Scripts\activate  # Windows PowerShell

3. Install dependencies:
pip install -r requirements.txt

4. Set up environment variables:
cp .env.example .env

Edit `.env` and add your API keys.

5. Run main.py

## Docker Setup
WIP