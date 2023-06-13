# Anime-Lang-Track-Corrector
An automation script that corrects undetermined and not applicable subtitle flags within mkv files for anime. 
It goes through each mkv file, track-by-track and checks for any undetermined or not applicable marked subtitles, then, at first, attempts to correct it by process of elimination. If not by that, then by extracting the subtitle file to a readable format, parsing each subtitle line-by-line, and using a language detection module to determine the overall language of the file. Then, if the overall detected language of the file meets the required threshhold (default is 70%), then the file language flag is set with that language.

Best used in tandem with https://github.com/iwalton3/media-scripts/tree/master/force-signs in my opinion. Use my script to correct any unmarked languages, and his to force the signs.

## Setup Instructions
### Linux (Ubuntu/Debian)
1. Run ``` git clone https://github.com/zachstultz/anime-lang-track-corrector ```
2. Run ```pip3 install -r requirements.txt```
3. Install mkvtoolnix ```sudo apt-get install mkvtoolnix```
4. Download the portable version of SubtitleEdit https://github.com/SubtitleEdit/subtitleedit/releases
5. Drop the contents into the se folder:
![image](https://github.com/zachstultz/anime-lang-track-corrector/assets/8385256/53e4d007-1035-478c-aa12-3d71a53e88dc)
6. Install the dependencies for SubtitleEdit (http://www.nikse.dk/subtitleedit/help#linux):
    ```
    sudo apt-get install mono-complete
    sudo apt-get install libhunspell-dev
    sudo apt-get install libmpv-dev (libmpv.so)
    sudo apt-get install tesseract-ocr
    sudo apt-get install vlc (already installed on some distros, SE uses (libvlc.so))
    sudo apt-get install ffmpeg (already installed on some distros)
    ```
7. Install XVFB
```
sudo apt-get install xvfb
```
8. Install libgtk2
```
sudo apt-get install libgtk2.0-0
```
8. Read the usage below and enjoy!
### Windows
1. Install mkvtoolnix https://mkvtoolnix.download/downloads.html#windows
2. Add the mkvtoolnix folder location as a PATH in windows.
3. Install SubtitleEdit https://github.com/SubtitleEdit/subtitleedit/releases
4. Add the SubtitleEdit folder location as a PATH in windows.
5. Read the usage below and enjoy!

## Usage
```
usage: anime_lang_track_corrector.py [-h] [-p PATH] [-f FILE] [-wh WEBHOOK]
                                     [-lmp LANG_MATCH_PERCENTAGE]

A script that corrects undetermined and not applicable subtitle flags within
mkv files for anime.

optional arguments:
  -h, --help            show this help message and exit
  -p PATH, --path PATH  The path to the anime folder to be scanned by
                        os.walk()
  -f FILE, --file FILE  The individual video file to be processed.
  -wh WEBHOOK, --webhook WEBHOOK
                        The optional discord webhook url to be pinged about
                        changes and errors.
  -lmp LANG_MATCH_PERCENTAGE, --lang-match-percentage LANG_MATCH_PERCENTAGE
                        The percentage of the detected file language required
                        for the language to be set.
```
Example for a path:
```
python3 anime_lang_track_corrector.py -p "/path/to/anime" -wh "WEBHOOK_URL" -lmp 70
```

Example for an individual file:
```
python3 anime_lang_track_corrector.py -f "/path/to/individual/file.mkv" -wh "WEBHOOK_URL" -lmp 70
```

## Goals
1. Rewrite script to use classes.
2. Massive code cleanup.
3. Simplify README setup.
4. Find alternative to SubtitleEdit, and eliminate that dependency.
5. Offer langdetect as an alternative to fasttext.
