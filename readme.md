# Anime-Lang-Track-Corrector
An automation script that corrects undetermined and not applicable subtitle flags within mkv files for anime. 
It goes through each mkv file, track-by-track and checks for any undetermined or not applicable marked subtitles, and at first, attempts to correct it by process of elimination. If not by that, then by extracting the subtitle, extracting the text from the subtitle, and determining the language of the file.

This project is still a heavy work-in-progress.
I do not consider this complete by any means, so you have been warned, test it on a small backup of your library first.

## How to Use
### Linux
1. Install mkvtoolnix ```apt-get install mkvtoolnix```
2. Run ``` git clone https://github.com/zachstultz/anime-lang-track-corrector ```
3. Run ```pip install -r requirements.txt```
4. Add the paths that you want scanned at the top of the file, into the appropriate string array.
5. Run ```anime_lang_track_corrector.py``` in command prompt or terminal.
### Windows
1. Download and install mkvtoolnix ```https://mkvtoolnix.download/downloads.html#windows```
2. Add mkvtoolnix folder location as PATH in windows.
3. Download or clone repo ``` git clone https://github.com/zachstultz/anime-lang-track-corrector ```
4. Run ```pip install -r requirements.txt```
5. Run ```anime_lang_track_corrector.py``` in command prompt or terminal.


## Common Use Case
So you have an anime mkv file that has dual audio, so it has two english subtitle files within it. A subtitle for all dialogue to be used with the japanese audio, and a signs & songs subtitle for use with the english audio.

But the problem is that the signs & songs language flag isn't set properly, it's showing as Undetermined or Not Applicable.

That is the purpose of this program, in my case, for use with plex. Plex can very easily pick subtitles and audio for you atuomatically based on your preferences, but it can't do this when the tracks aren't properly labeled with their correct language.
