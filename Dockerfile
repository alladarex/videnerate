# Small Python base image
FROM python:3.12-slim

# System packages we need:
# - ffmpeg: audio and video processing
# - the rest: Qt needs these to open a window on Linux (X11)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libdbus-1-3 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-sync1 \
        libxcb-xfixes0 \
        libxcb-xkb1 \
    && rm -rf /var/lib/apt/lists/*

# App lives here
WORKDIR /videnerate

# Install Python deps first so this layer is cached
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Make the app folder writable for any user.
# This lets you run the container with --user <uid>:<gid> and still
# save files into projects/ without permission errors.
RUN chmod -R a+rwX /videnerate

# HOME points to a writable folder so Qt and pip don't complain
# when the container runs as a random UID.
ENV HOME=/tmp \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=xcb

# Start the app
CMD ["python", "main.py"]
