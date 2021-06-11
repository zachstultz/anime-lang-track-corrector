# Anime-Lang-Track-Corrector
An automation script that corrects undetermined and not applicable subtitle flags within mkv files for anime. 
It goes through each mkv file, track-by-track and checks for any undetermined or not applicable marked subtitles, and at first, attempts to correct it by process of elimination. If not by that, then by extracting the subtitle, extracting the text from the subtitle, and determining the language of the file.

This project is still a heavy work-in-progress.
I do not consider this complete by any means, so you have been warned, test it on a small backup of your library first.

## Common Use Case
So you have an anime mkv file that has dual audio, so it has two english subtitle files within it. A subtitle for all disalouge to be used with the japanese audio, and a signs & songs subtitle for use with the english audio.

But the problem is that the signs & songs language flag isn't set properly, it's showing as Undetermined or Not Applicable.

That is the purpose of this program, in my case, for use with plex. Plex can very easily pick subtitles and audio for you atuomatically based on your preferences, but it can't do this when the tracks aren't properly labeled with their correct language.

## How to Use
1. Run pip install -r requirements.txt (coming soon, haven't made it yet)
2. Add the paths that you want scanned at the top of the file, in the empty string array.
2. Run anime_lang_track_corrector.py in command prompt or terminal.