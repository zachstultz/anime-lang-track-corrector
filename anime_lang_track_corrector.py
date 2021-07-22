import os
import platform
import re
import subprocess
import pymkv
import fasttext
from pysubparser import parser
from discord_webhook import DiscordWebhook
from datetime import datetime
from chardet.universaldetector import UniversalDetector


# FastText Model Location
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PRETRAINED_MODEL_PATH = os.path.join(ROOT_DIR, 'lid.176.bin')
model = fasttext.load_model(PRETRAINED_MODEL_PATH)

# Used to determine execution time at the end
startTime = datetime.now()

# Paths you want scanned
paths = [""]

# OPTIONAL Discord Webhook
discord_webhook_url = ""

# Stuff printed at the end
items_changed = []
problematic_children = []

# The linux location for SE
path_to_subtitle_edit_linux = "/data/docker/se/"

# Signs & Full keyword arrays, add any keywords you want to be searched for
signs_keywords = ["sign", "music", "song"]
full_keywords = ["full", "dialog", "dialogue", "english subs"]

# Removes the file if it exists, used for cleaning up after FastText detection
def remove_file(file):
    if(os.path.isfile(file)):
        os.remove(file)
    else:
        print("\t\tFile does not exist, if it does, the file could not be deleted.")

# Detects the encoding of the supplied subtitle file
def detect_subtitle_encoding(output_file_with_path):
    detector = UniversalDetector()
    try:
        for line in open(output_file_with_path, 'rb'):
            detector.feed(line)
            if detector.done: break
        detector.close()
        encoding = detector.result['encoding']
    except FileNotFoundError:
        print("File not found.")
        print("Defaulting to UTF-8")
        encoding = "UTF-8"
    return encoding

# Sends a discord message
def send_discord_message(message):
    if discord_webhook_url != "":
        webhook = DiscordWebhook(url=discord_webhook_url, content=message, rate_limit_retry=True)
        response = webhook.execute()
    else:
        print("Discord hook cannot be empty!")
        
# Prints the information about the given track
def print_track_info(track):
    print("\t\t" + "Track: " + str(track.track_id))
    print("\t\t" + "Type: " + str(track._track_type))
    print("\t\t" + "Name: " + str(track.track_name))
    print("\t\t" + "Language: " + str(track.language) + "\n")

# Determines and sets the file extension
def set_extension(track):
    extension = ""
    if(track.track_codec == ("SubStationAlpha" or "Advanced SubStation Alpha")):
        extension = "ass"
    elif(track.track_codec == ("SubRip/SRT")):
        extension = "srt"
    elif(track.track_codec == ("HDMV PGS")):
        extension = "pgs"
    return extension

# The execution start of the program
if discord_webhook_url != "":
    send_discord_message("[START]-------------------------------------------[START]")
    send_discord_message("Start Time: " + str(datetime.now()))
    send_discord_message("Script: anime_lang_track_corrector.py")
for path in paths:
    if os.path.isdir(path):
        os.chdir(path)
        for root, dirs, files, in os.walk(path):
            cleaned_files = []
            for file in files:
                if(not file.startswith('.') and file.endswith('.mkv')):
                    cleaned_files.append(file)
            print("\nCurrent Path: ", root + "\nDirectories: ", dirs)
            print("Files: ", cleaned_files)
            for file in cleaned_files:
                full_path = os.path.join(root, file)
                file_without_extension = os.path.splitext(full_path)[0]
                if os.path.isfile(full_path):
                    print("\n\t" + "File: " + file)
                    fileEndsWithMKV = file.endswith(".mkv")
                    fileIsTrailer = str(re.search('trailer', str(file), re.IGNORECASE))
                    fileBeginsWithDot = file.startswith('.')
                    if((fileEndsWithMKV and fileIsTrailer == "None") and not fileBeginsWithDot):
                        try:
                            isMKVFile = pymkv.verify_matroska(full_path)
                            if isMKVFile:
                                print("\t" + "isValidMKV: " + str(isMKVFile))
                                isSupportedByMKVMerge = pymkv.verify_supported(full_path)
                                if isSupportedByMKVMerge:
                                    print("\t" + "isSupportedByMKVMerge: " + str(isSupportedByMKVMerge))
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
                                        print_track_info(track)
                                        if((track._track_type == "subtitles") and (track.language == "zxx" or track.language == "und")):
                                            print("\t\t" + "No Linguistic Content/Not Applicable track found!")
                                            print("\t\t" + "Track language is unknown.")
                                            extension = set_extension(track)
                                            if(str(track.track_name) != "None"):
                                                for sign in signs_keywords:
                                                    sign = str(re.search(sign, track.track_name, re.IGNORECASE))
                                                    contains_english_keyword = str(re.search('english', str(track.track_name), re.IGNORECASE))
                                                    contains_english_keyword_two = str(re.search(r"\beng\b", str(track.track_name), re.IGNORECASE))
                                                    if(sign != "None"):
                                                        print("\t\t" + "Track name contains a Signs keyword.")
                                                        if(total_audio_and_subtitle_tracks > 0):
                                                            if((total_audio_and_subtitle_tracks % 2) == 0):
                                                                if(unknown_audio_track_count == 0 and unknown_subtitle_track_count == 1):
                                                                    if(total_audio_and_subtitle_tracks - (jpn_audio_track_count + eng_audio_track_count + jpn_subtitle_track_count + eng_subtitle_track_count) == unknown_subtitle_track_count):
                                                                        print("\tTrack determined to be english through process of elimination.")
                                                                        subprocess.Popen(["mkvpropedit", full_path,"--edit","track:" + str(track.track_id+1),"--set","language=eng"])
                                                                        print("\tTrack set to english.")
                                                                        items_changed.append("Track set to english: " + full_path + " Track: " + str(track.track_id+1))
                                                                        message = "Track set to english: " + full_path + " Track: " + str(track.track_id+1)
                                                                        send_discord_message(message)
                                                                        break
                                                    elif(eng_audio_track_count == 0):
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
                                                                        send_discord_message(message)
                                                                        break
                                                    elif(contains_english_keyword != "None" or contains_english_keyword_two != "None"):
                                                        print("\t\t" + "English keyword found in track name.")
                                                        print("\t\t" + "Setting track language to english.")
                                                        subprocess.Popen(["mkvpropedit", full_path,"--edit","track:" + str(track.track_id+1),"--set","language=eng"])
                                                        print("\t\t" + "Track set to english.")
                                                        items_changed.append("Track set to english: " + full_path + " Track: " + str(track.track_id+1))
                                                        message = "Track set to english: " + full_path + " Track: " + str(track.track_id+1)
                                                        send_discord_message(message)
                                                        break
                                                    else:
                                                        print("\t\t" + "Language could not be determined through process of elimination.")
                                                        print("\t\t" + "File will be extracted and detection will be attempted.")
                                                        print("\t\t" + "Extracting test file to " + root)         
                                                        output_file = "language_detection_test"+"."+extension
                                                        output_file_with_path = os.path.join(root, output_file)
                                                        call = "mkvextract tracks " + "\"" + full_path + "\"" + " " + str(track.track_id) + ":" + "\"" + output_file_with_path + "\""
                                                        call = subprocess.run(call, shell=True, capture_output=True, text=True)
                                                        if(os.path.isfile(output_file_with_path) and call.returncode == 0):
                                                            print("\t\tExtraction successfull.")
                                                            if(platform.system() == "Windows"):
                                                                call = "SubtitleEdit /convert " + "\"\\\\?\\" + output_file_with_path + "\" srt /RemoveFormatting /MergeSameTexts /overwrite"
                                                            elif(platform.system() == "Linux"):
                                                                call = "xvfb-run -a mono "+path_to_subtitle_edit_linux+"SubtitleEdit.exe /convert " + "\""  + output_file_with_path + "\" srt /RemoveFormatting /MergeSameTexts /overwrite"
                                                            call = subprocess.run(call, shell=True)
                                                            converted_file = os.path.splitext(output_file_with_path)[0] + ".srt"
                                                            subtitles = parser.parse(converted_file, subtitle_type="srt", encoding=detect_subtitle_encoding(converted_file))
                                                            output = []
                                                            for subtitle in subtitles:
                                                                output.append(subtitle)
                                                            total_lines = output.__len__()
                                                            total_english = 0
                                                            for subtitle in output:
                                                                try:
                                                                    filtered = re.sub(r"[-()\"#/@%\\;:<>{}`+=~|.!?,]", "", subtitle.text)
                                                                    if(filtered != ""):
                                                                        result = re.sub(r"[-()\"#/@%\\;:<>{}`'+=~|.!?,]", "", str(model.predict(filtered)[0]).split("__label__",1)[1])
                                                                        print("\t\tLanguage Detected: " + result + " on " + filtered + "\t")
                                                                        if(result == "en" or result == "eng"):
                                                                            total_english += 1
                                                                    else:
                                                                        print("\t\tEmpty filtered subtitle.")
                                                                except Exception:
                                                                    error = "Error determining result of subtitle: " + str(subtitle.text)
                                                                    print(error)
                                                                    problematic_children.append(error)
                                                            match_result_percent = str((total_english/total_lines)*100) + "%"
                                                            if ((total_english/total_lines)*100 > 70):
                                                                print("Subtitle file detected as english.")
                                                                print("Setting english on sub file within mkv")
                                                                subprocess.Popen(["mkvpropedit", full_path,"--edit","track:" + str(track.track_id+1),"--set","language=eng"])
                                                                print("Track set to english.")
                                                                items_changed.append("Track set to english: " + full_path + " Track: " + str(track.track_id+1))
                                                                message = "Track set to english: " + full_path + " Track: " + str(track.track_id+1)
                                                                send_discord_message(message)
                                                                remove_file(output_file_with_path)
                                                                remove_file(converted_file)
                                                                if(not os.path.isfile(output_file_with_path)):
                                                                    print("Test files removed")
                                                                else:
                                                                    print("Failed to remove file: " + output_file_with_path)
                                                                    problematic_children.append("Failed to remove file: " +output_file_with_path)
                                                                break
                                                            else:
                                                                remove_file(output_file_with_path)
                                                                remove_file(converted_file)
                                                                print("Match: " + match_result_percent + "\n\t\tSubtitle match below 70%, no match found.\n")
                                                                message = "Match: " + match_result_percent + "\nSubtitle match below 70%, no match found.\n" + full_path + " Track: " + str(track.track_id+1)
                                                                problematic_children.append(message)
                                                                send_discord_message(message)
                                                                break
                                                        else:
                                                            print("Extraction failed.\n")
                                                            problematic_children.append("Extraction failed: " + output_file_with_path)
                                            else:
                                                print("\t\tTrack name is empty, TRACK: " + str(track.track_id) + "on " + full_path)
                                                problematic_children.append("Track name is empty, TRACK: " + str(track.track_id) + " on " + full_path)
                                        else:
                                            print("\t\t" + "No matching track found.\n")
                                else:
                                    print("\t" + "isSupportedByMKVMerge: " + str(isSupportedByMKVMerge))
                            else:
                                print("\t" + "isValidMKV: " + str(isMKVFile))
                        except KeyError:
                            print("\t" + "Error with file: " + file)
                            problematic_children.append("Error with file: " + file)
                    else:
                        print("\t" + "isMKVFile: " + str((fileEndsWithMKV and fileIsTrailer == "None") and not fileBeginsWithDot))                             
                else:
                    print("Not a valid file.\n")
    else :
        print("Invalid Directory: " + path + "\n")
        problematic_children.append("Invalid Directory: " + path)

if(len(problematic_children) != 0):
    if discord_webhook_url != "":
        send_discord_message("--- Problematic Files/Directories ---")
    print("\n--- Problematic Files/Directories ---")
    for problem in problematic_children: 
        print(str(problem) + "\n")
        send_discord_message(str(problem))
if(len(items_changed) != 0):
    if discord_webhook_url != "":
        send_discord_message("\n--- Items Changed ---")
    print("\n--- Items Changed ---")
    for item in items_changed:
        print(str(item) + "\n")
        send_discord_message(str(item))
        
if discord_webhook_url != "":
    send_discord_message("\nTotal Execution Time: " + str((datetime.now() - startTime)))    
print(("\nTotal Execution Time: " + str((datetime.now() - startTime))))
send_discord_message("[END]-------------------------------------------[END]")
