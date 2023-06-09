(I wrote this when I was relearning python after having not used it for years. The code base is pretty rough, it still accomplishes what I wanted it to, but badly needs a complete rewrite from the ground up. Just wanted to give a heads up to any fellow devs looking at the code.)

# Anime-Lang-Track-Corrector
An automation script that corrects undetermined and not applicable subtitle flags within mkv files for anime. 
It goes through each mkv file, track-by-track and checks for any undetermined or not applicable marked subtitles, then, at first, attempts to correct it by process of elimination. If not by that, then by extracting the subtitle file to a readable format, parsing each subtitle line-by-line, and using a language detection module to determine the overall language of the file. Then, if the overall detected language of the file meets the required threshhold (default is 70%), then the file language flag is set with that language.

Best used in tandem with https://github.com/iwalton3/media-scripts/tree/master/force-signs in my opinion. Use my script to correct any unmarked languages, and his to force the signs.

## Common Use Case
You have an anime mkv file that has dual audio, so it has two english subtitle files within it. A subtitle for all dialogue to be used with the japanese audio, and a signs & songs subtitle for use with the english audio. But the problem is that the signs & songs or full subtitles language flag isn't set properly, it's showing as Undetermined or Not Applicable.

That is the purpose of this program, in my case, for use with plex. Plex can very easily pick subtitles and audio for you automatically based on your preferences, but it can't do this when the tracks aren't marked with their proper language.

## Setup Instructions
### Linux (Ubuntu/Debian)
1. Run ``` git clone https://github.com/zachstultz/anime-lang-track-corrector ```
2. Run ```pip3 install -r requirements.txt```
3. Install mkvtoolnix ```sudo apt-get install mkvtoolnix```
4. Download the portable version of Subtitle Edit (and not the installer). https://github.com/SubtitleEdit/subtitleedit/releases
5. Install the dependencies for Subtitle Edit (http://www.nikse.dk/subtitleedit/help#linux):

    Packages required for Ubuntu based distros:
    ```
    sudo apt-get install mono-complete
    sudo apt-get install libhunspell-dev
    sudo apt-get install libmpv-dev (libmpv.so)
    sudo apt-get install tesseract-ocr
    sudo apt-get install vlc (already installed on some distros, SE uses (libvlc.so))
    sudo apt-get install ffmpeg (already installed on some distros)
    ```
6. Install XVFB
```
sudo apt-get install xvfb
```
7. Install libgtk2
```
sudo apt-get install libgtk2.0-0
```
8. Update path_to_subtitle_edit_linux at the top of the script with the path to that folder.
![Screen Shot 2021-09-15 at 3 24 02 PM](https://user-images.githubusercontent.com/8385256/133504275-382ebb15-e0de-4e15-8692-af1dc8acf748.png)
9. Download the fasttext language model. Either the uncompressed(lid.176.bin) or compressed(lid.176.ftz). https://fasttext.cc/docs/en/language-identification.html
10. Drag and drop the model into the root folder of the script.
![Screen Shot 2021-09-15 at 3 34 30 PM](https://user-images.githubusercontent.com/8385256/133505641-9b37a2ce-2679-452a-812b-5e3a72a86865.png)
11. Change the model file name in the script, contained in the PRETRAINED_MODEL_PATH. (if you're using uncompressed, it's already set).
![Screen Shot 2021-09-15 at 3 31 35 PM](https://user-images.githubusercontent.com/8385256/133505669-78bf2ec8-297c-4dc3-b79a-ba6c11501e09.png)
12. Read the usage below and enjoy!
### Windows
1. Download and install mkvtoolnix ```https://mkvtoolnix.download/downloads.html#windows```
2. Add the mkvtoolnix folder location as a PATH in windows.
3. Download Subtitle Edit, install, and add the folder location as a PATH in windows. https://github.com/SubtitleEdit/subtitleedit/releases
4. Download the fasttext language model. Either the uncompressed(lid.176.bin) or compressed(lid.176.ftz). https://fasttext.cc/docs/en/language-identification.html
5. Drag and drop the model into the root folder of the script.
![Screen Shot 2021-09-15 at 3 34 30 PM](https://user-images.githubusercontent.com/8385256/133505641-9b37a2ce-2679-452a-812b-5e3a72a86865.png)
6. Change the model file name in the script, contained in the PRETRAINED_MODEL_PATH. (if you're using uncompressed, it's already set).
![Screen Shot 2021-09-15 at 3 31 35 PM](https://user-images.githubusercontent.com/8385256/133505669-78bf2ec8-297c-4dc3-b79a-ba6c11501e09.png)
7. Read the usage below and enjoy!

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
4. Find alternative to Subtitles Edit, and eliminate that dependency.
5. Offer langdetect as an alternative to fasttext.
