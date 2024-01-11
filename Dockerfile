# Use a specific version of the Python image
FROM python:3.11.4-slim-bookworm

# Set the working directory to /app
WORKDIR /app

# Create a new user called "appuser"
RUN useradd -m appuser
ARG PUID=1000
ARG PGID=1000

# Set ownership to appuser and switch to "appuser"
RUN apt-get update
RUN groupmod -o -g "$PGID" appuser && usermod -o -u "$PUID" appuser

# Allow users to specify UMASK (default value is 022)
ENV UMASK 022
RUN umask "$UMASK"

# Copy the current directory contents into the container at /app
COPY --chown=appuser:appuser . .

# Install necessary packages and requirements
RUN apt-get install -y tzdata nano mkvtoolnix mono-complete libhunspell-dev libmpv-dev tesseract-ocr vlc ffmpeg xvfb libgtk2.0-0 build-essential
RUN pip3 install --no-cache-dir -r requirements.txt

# Clean up
RUN apt-get autoremove -y
RUN rm -rf /var/lib/apt/lists/*

# Switch to "appuser"
USER appuser

# Set the default CMD arguments for the script
CMD python3 -u anime_lang_track_corrector.py --path="$PATH_TO_DIR" --file="$FILE" --webhook="$WEBHOOK" --lang-match-percentage="$LANG_MATCH_PERCENTAGE" --se_path="$SE_PATH"