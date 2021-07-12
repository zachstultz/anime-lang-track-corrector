from posixpath import basename
import ass
import os
from langdetect.lang_detect_exception import LangDetectException
import pymkv
import re
import langdetect
from pymkv.MKVTrack import MKVTrack
import subprocess
from pysubparser import parser
from pysubparser.cleaners import ascii, brackets, formatting, lower_case
from discord_webhook import DiscordWebhook
from datetime import datetime
import platform

startTime = datetime.now()
paths = [""]

# Optional
discord_webhook_url = ""

items_changed = []
problematic_children = []

for path in paths:
    if os.path.isdir(path) :
        os.chdir(path)
        for root, dirs, files, in os.walk(path):
            print("\nCurrent Path: ", root + "\nDirectories: ", dirs)
            print("Files: ", files)
            for file in files:
                full_path = os.path.join(root, file)
                if os.path.isfile(full_path):
                    print("\n\t" + "File: " + file)
                    if((file.endswith(".mkv") and (not str(file).__contains__("trailer") or not str(file).__contains__("Trailer"))) and not str(file).startswith("._")):
                        try:
                            if pymkv.verify_matroska(full_path):
                                print("\t" + "isValidMKV: True")
                                if pymkv.verify_supported(full_path):
                                    print("\t" + "isSupportedByMKVMerge: True")
                                    mkv = pymkv.MKVFile(full_path)
                                    tracks = mkv.get_track()
                                    print("\t\t--- Tracks [" + str(tracks.__len__()) + "] ---")
                                    jpn_audio_track_count = 0
                                    eng_audio_track_count = 0

                                    jpn_subtitle_track_count = 0
                                    eng_subtitle_track_count = 0

                                    unknown_audio_track_count = 0
                                    unknown_subtitle_track_count = 0

                                    total_audio_and_subtitle_tracks = 0
                                    for track in tracks:
                                        if track._track_type == "audio":
                                            if track.language == "jpn" or track.language == "jp":
                                                jpn_audio_track_count += 1
                                            elif track.language == "eng" or track.language == "en":
                                                eng_audio_track_count += 1
                                            else:
                                                unknown_audio_track_count += 1
                                        if track._track_type == "subtitles":
                                            if track.language == "jpn" or track.language == "jp":
                                                jpn_subtitle_track_count += 1
                                            elif track.language == "eng" or track.language == "en":
                                                eng_subtitle_track_count += 1
                                            else:
                                                unknown_subtitle_track_count += 1
                                    total_audio_and_subtitle_tracks = jpn_audio_track_count + eng_audio_track_count + jpn_subtitle_track_count + eng_subtitle_track_count + unknown_audio_track_count + unknown_subtitle_track_count
                                    for track in tracks:
                                        print("\t\t" + "Track: " + str(track.track_id))
                                        print("\t\t" + "Type: " + str(track._track_type))
                                        print("\t\t" + "Name: " + str(track.track_name))
                                        print("\t\t" + "Language: " + str(track.language) + "\n")
                                        if (track.language == "zxx" or track.language == "und") and track._track_type == "subtitles" and ((str(track.track_name).__contains__("Sign") 
                                        or str(track.track_name).__contains__("sign")) or (str(track.track_name).__contains__("Song") or str(track.track_name).__contains__("song")) or (str(track.track_name).__contains__("Music") or str(track.track_name).__contains__("music"))):
                                            print("\t\t" + "No Linguistic Content/Not Applicable track found!")
                                            print("\t\t" + "Track language is unknown.")
                                            print("\t\t" + "Track name contains Signs or Song or Music keyword.")
                                            if(total_audio_and_subtitle_tracks > 0):
                                                if((total_audio_and_subtitle_tracks % 2) == 0):
                                                    if(unknown_audio_track_count == 0 and unknown_subtitle_track_count == 1):
                                                        if(total_audio_and_subtitle_tracks - (jpn_audio_track_count + eng_audio_track_count + jpn_subtitle_track_count + eng_subtitle_track_count) == unknown_subtitle_track_count):
                                                            print("\tTrack determined to be english through process of elimination.")
                                                            subprocess.Popen(["mkvpropedit", full_path,"--edit","track:" + str(track.track_id+1),"--set","language=eng"])
                                                            print("\tTrack set to english.")
                                                            items_changed.append("Track set to english: " + full_path + " Track: " + str(track.track_id+1))
                                                            message = "Track set to english: " + full_path + " Track: " + str(track.track_id+1)
                                                            if not discord_webhook_url:
                                                                webhook = DiscordWebhook(url=discord_webhook_url, content=message)
                                                                response = webhook.execute()
                                            elif(track._track_type == "subtitles"):
                                                print("\t\t" + "Extracting file to " + root)
                                                extension = "txt"
                                                if(track.track_codec == ("SubStationAlpha" or "Advanced SubStation Alpha")):
                                                    extension = "ass"             
                                                output_file = "language_detection_test"+"."+extension
                                                output_file_with_path = os.path.join(root, output_file)
                                                call = "mkvextract tracks " + "\"" + full_path + "\"" + " " + str(track.track_id) + ":" + "\"" + output_file_with_path + "\""
                                                subprocess.call(call)
                                                if(os.path.isfile(output_file_with_path)):
                                                    print("Extraction successfull.")
                                                    subtitles = parser.parse(output_file_with_path)
                                                    cleaned_subtitles = brackets.clean(formatting.clean(subtitles))
                                                    output = []
                                                    for subtitle in cleaned_subtitles:
                                                        cleaned = re.sub(r'[0-9]', '', re.sub(r'{.+?}', ' ', subtitle.text))
                                                        removeSpecialChars = cleaned.translate ({ord(c): " " for c in "!@#$%^&*()[]{};:,./<>?\|`~-=_+"})
                                                        removeSingleChars =  re.sub(r"\b[a-zA-Z]\b", " ", removeSpecialChars)
                                                        pattern = re.compile(r'\s+')
                                                        removeSingleChars = re.sub(pattern, ' ', removeSingleChars)
                                                        if(not removeSingleChars or removeSingleChars.isspace()):
                                                            print()    
                                                        else:
                                                            output.append(removeSingleChars)
                                                    total_lines = output.__len__()
                                                    total_english = 0
                                                    langdetect.DetectorFactory.seed = 0
                                                    for s in output:
                                                        try:
                                                            print("Language Detected: " + langdetect.detect(s))
                                                            if(langdetect.detect(s) == ("en" or "eng")):
                                                                total_english += 1
                                                            if(langdetect.detect(s) != ("en" or "eng")):
                                                                print(s)
                                                        except LangDetectException:
                                                            print("LangDetectException")
                                                    print((total_english/total_lines)*100)
                                                    if ((total_english/total_lines)*100 > 50):
                                                        print("Subtitle file detected as english.")
                                                        print("Setting english on sub file within mkv")
                                                        subprocess.Popen(["mkvpropedit", full_path,"--edit","track:" + str(track.track_id+1),"--set","language=eng"])
                                                        print("Track set to english.")
                                                        items_changed.append("Track set to english: " + full_path + " Track: " + str(track.track_id+1))
                                                        message = "Track set to english: " + full_path + " Track: " + str(track.track_id+1)
                                                        if not discord_webhook_url:
                                                            webhook = DiscordWebhook(url=discord_webhook_url, content=message)
                                                            response = webhook.execute()
                                                        os.remove(output_file_with_path)
                                                        if(not os.path.isfile(output_file_with_path)):
                                                            print("Test file removed")
                                                        else:
                                                            print("Failed to remove file: " + output_file_with_path)
                                                            problematic_children.append("Failed to remove file: " +output_file_with_path)
                                                    else:
                                                        print("Subtitle match percent below 50%, no match found.\n")
                                                        message = "Subtitle match percent below 50%, no match found.\n" + full_path + " Track: " + str(track.track_id+1)
                                                        if not discord_webhook_url:
                                                            webhook = DiscordWebhook(url=discord_webhook_url, content=message)
                                                            response = webhook.execute()
                                                else:
                                                    print("Extraction failed.\n")
                                                    problematic_children.append("Extraction failed: " + output_file_with_path)
                                        elif (((track.language == "zxx" or track.language == "und") and eng_audio_track_count == 0) and (full_path.__contains__("anime") or full_path.__contains__("Anime"))):
                                            if(track._track_type == "subtitles"):
                                                print("\t\t" + "Track language is unknown.")
                                                print("\t\t" + "No recognized name track.")
                                                if jpn_subtitle_track_count == 0 and jpn_audio_track_count == 1:
                                                    if eng_subtitle_track_count == 0 and eng_audio_track_count == 0:
                                                        if unknown_audio_track_count == 0 and unknown_subtitle_track_count == 1:
                                                            if (total_audio_and_subtitle_tracks - (jpn_audio_track_count + jpn_subtitle_track_count)) == unknown_subtitle_track_count:
                                                                print("\tTrack determined to be english through process of elimination.")
                                                                subprocess.Popen(["mkvpropedit", full_path,"--edit","track:" + str(track.track_id+1),"--set","language=eng"])
                                                                print("\tTrack set to english.")
                                                                message = "Track set to english: " + full_path + " Track: " + str(track.track_id+1)
                                                                items_changed.append(message)
                                                                if not discord_webhook_url:
                                                                    webhook = DiscordWebhook(url=discord_webhook_url, content=message)
                                                                    response = webhook.execute()
                                        else:
                                            print("\t\t" + "No matching track found.\n")
                                else:
                                    print("\t" + "isSupportedByMKVMerge: False\n")
                            else:
                                print("\t" + "isValidMKV: False\n")
                        except KeyError:
                            print("\t" + "Error with file: " + file)
                            problematic_children.append("Error with file: " + file)
                    else:
                        print("\t" + "isMKVFile: False\n")                                       
                else:
                    print("Not a valid file.\n")
    else :
        print("Invalid Directory\n")

if(problematic_children.count != 0):
    if not discord_webhook_url:
        webhook = DiscordWebhook(url=discord_webhook_url, content=str("\n--- Problematic Files/Directories ---"))
        response = webhook.execute()
        webhook = DiscordWebhook(url=discord_webhook_url, content=str(problematic_children))
        response = webhook.execute()
    print("\n--- Problematic Files/Directories ---")
    for problem in problematic_children: 
        print(str(problem) + "\n")
if(items_changed.count != 0):
    if not discord_webhook_url:
        webhook = DiscordWebhook(url=discord_webhook_url, content=str("\n--- Items Changed ---"))
        response = webhook.execute()
        webhook = DiscordWebhook(url=discord_webhook_url, content=str(items_changed))
        response = webhook.execute()
    print("\n--- Items Changed ---")
    for item in items_changed:
        print(str(item) + "\n")
if not discord_webhook_url:
    webhook = DiscordWebhook(url=discord_webhook_url, content=str("\nTotal Execution Time: " + (datetime.now() - startTime)))
    response = webhook.execute()
