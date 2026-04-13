import os
import requests
import ffmpeg
from pathlib import Path
from typing import List, Dict, Union
from config import PEXELS_API_KEY, PIXABAY_API_KEY

MEDIA_SUBDIR = "media"