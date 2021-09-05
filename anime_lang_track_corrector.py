from genericpath import isfile
import os
import sys
import platform
import re
import subprocess
from typing import Text
import pymkv
import fasttext
import argparse
from pysubparser import parser
from discord_webhook import DiscordWebhook
from datetime import datetime
from chardet.universaldetector import UniversalDetector

p = argparse.ArgumentParser(description="My anime language track corrector script.")
p.add_argument('path', help="The path to be passed in and scanned.", default="", nargs="?")
p.add_argument('webhook_url', help="The optional discord webhook url", default="", nargs="?")
args = p.parse_args()

# The OS of the user
user_os = platform.system()

# FastText Model Location
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PRETRAINED_MODEL_PATH = os.path.join(ROOT_DIR, 'lid.176.bin')
model = fasttext.load_model(PRETRAINED_MODEL_PATH)

# The required percentage that must be met when detecting an individual language with FastText
required_lang_match_percentage = 70

# Used to determine the total execution time at the end
startTime = datetime.now()

# passed path to be scanned
path = args.path
path = os.path.dirname(path)
path_with_file = args.path

# OPTIONAL Discord Webhook
discord_webhook_url = args.webhook_url

# Stuff printed at the end
items_changed = []
problematic_children = []

# The linux location for SE
path_to_subtitle_edit_linux = ""

# Signs & Full keyword arrays, add any keywords you want to be searched for
signs_keywords = ["sign", "music", "song"]
full_keywords = ["full", "dialog", "dialogue", "english subs"]

# Folders to be ignored
ignored_folders = [""]

# Removes the file if it exists, used for cleaning up after FastText detection
def remove_file(file):
    if(os.path.isfile(file)):
        idx_file = os.path.splitext(file)[0] + ".idx"
        if(str(file).endswith(".sub") and os.path.isfile(idx_file)):
            remove_file(idx_file)
        os.remove(file)
        if(not os.path.isfile(file)):
            print("\t\tFile removed: " + file)
        else:
            send_error_message("\t\tFailed to remove file: " + file)
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
        send_error_message("File not found.")
        send_error_message("Defaulting to UTF-8")
        encoding = "UTF-8"
    return encoding

def send_error_message(message):
    problematic_children.append(message)
    send_discord_message(message)
    print(message)

def send_change_message(message):
    items_changed.append(message)
    send_discord_message(message)
    print(message)

# Sends a discord message
def send_discord_message(message):
    if discord_webhook_url != "":
        webhook = DiscordWebhook(url=discord_webhook_url, content=message, rate_limit_retry=True)
        response = webhook.execute()
        
# Prints the information about the given track
def print_track_info(track):
    print("\n\t\t" + "Track: " + str(track.track_id))
    print("\t\t" + "Type: " + str(track._track_type))
    print("\t\t" + "Name: " + str(track.track_name))
    print("\t\t" + "Language: " + str(track.language) + "\n")

# Determines and sets the file extension
def set_extension(track):
    extension = ""
    if(track.track_codec == ("SubStationAlpha" or "AdvancedSubStationAlpha")):
        extension = "ass"
    elif(track.track_codec == ("SubRip/SRT")):
        extension = "srt"
    elif(track.track_codec == ("HDMV PGS")):
        extension = "pgs"
    elif(track.track_codec == ("VobSub")):
        extension = "sub"
    return extension

# Removes hidden files from list, useful for MacOS
def remove_hidden_files(files, root):
    for file in files[:]:
        if(file.startswith(".") and os.path.isfile(os.path.join(root, file))):
            files.remove(file)

def extract_output_subtitle_file_and_convert(file_name, track, full_path):
    outputted_file = os.path.join(root, file_name)
    call = "mkvextract tracks " + "\"" + full_path + "\"" + " " + str(track.track_id) + ":" + "\"" + os.path.join(root, file_name) + "\""
    call = subprocess.run(call, shell=True, capture_output=True, text=True)
    if(os.path.isfile(outputted_file) and call.returncode == 0):
        print("\t\tExtraction successfull.")
        return convert_subtitle_file(outputted_file)
    else:
        send_error_message("Extraction failed: " + outputted_file + "\n")

def set_track_language(path, track, language_code):
    subprocess.Popen(["mkvpropedit", path,"--edit","track:" + str(track.track_id+1),"--set","language=" + language_code])
    #subprocess.Popen(["mkvpropedit", path,"--edit","track:" + str(track.track_id+1),"--set","language-ietf=" + language_code])
    send_change_message("Track set to " + language_code + ": " + full_path + " Track: " + str(track.track_id+1))

def check_and_set_result_two(match_result, full_path, track, lang_code, output_file_with_path):
    match_result_percent = str(match_result) + "%"
    if (match_result > required_lang_match_percentage):
        print("\t\tSubtitle file detected as english.")
        print("\t\tSetting english on sub file within mkv")
        set_track_language(full_path, track, lang_code)
        message = "\n\t\tFile: " + file + "\n\t\tMatch: " + match_result_percent
        send_discord_message(message)
        remove_file(output_file_with_path)
        return 1
    else:
        send_error_message("\n\t\tFile: " + file + "\n\t\tMatch: " + match_result_percent + "\n\t\tSubtitle match below " + str(required_lang_match_percentage) + "%, no match found.\n")
        remove_file(output_file_with_path)
        return 0

def check_and_set_result(match_result, full_path, track, lang_code, output_file_with_path, original_subtitle_array):
    if (match_result > required_lang_match_percentage):
        print("\t\tSubtitle file detected as english.")
        print("\t\tSetting english on sub file within mkv")
        set_track_language(full_path, track, lang_code)
        remove_file(output_file_with_path)
    else:
        match_result_percent = str(match_result) + "%"
        send_error_message("\n\t\tFile: " + file + "\n\t\tMatch: " + match_result_percent + "\n\t\tSubtitle match below " + str(required_lang_match_percentage) + "%, no match found.\n")
        #if(match_result > 5):
            #remove_signs_and_subs(files, file, original_subtitle_array)
        remove_file(output_file_with_path)

def detect_subs_via_fasttext():
    if(search_track_for_language_keyword(path, track, "eng") == 0):
        print("\t\t" + "File will be extracted and detection will be attempted.")
        print("\t\t" + "Extracting test file to " + root)
        output_file_with_path = extract_output_subtitle_file_and_convert("lang_test"+"."+extension, track, full_path)
        subtitle_lines_array = parse_subtitle_lines_into_array(output_file_with_path)
        match_result = evaluate_subtitle_lines(subtitle_lines_array)
        check_and_set_result(match_result, full_path, track, "eng", output_file_with_path, subtitle_lines_array)

def clean_subtitle_lines(lines):
    clean = []
    for line in lines:
        line = re.sub(r"[-()\"#/@%\\;:<>{}`+=~|.!?,]", "", line.text)
        line = re.sub(r"[\d\.]+", "", line)
        if(len(line) > 1 and line != ""):
            clean.append(line)
    return clean

def clean_subtitle_line(line):
    line = re.sub(r"[-()\"#/@%\\;:<>{}`+=~|.!?,]", "", line)
    line = re.sub(r"[\d\.]+", "", line)
    return line

def evaluate_subtitle_lines(lines):
    total_lines = lines.__len__()
    total_english = 0
    for subtitle in lines:
        try:
            pass_text = ""
            if(hasattr(subtitle, "text") and subtitle.text is not None):
                pass_text = subtitle.text
            elif(subtitle != "" or subtitle is not None):
                pass_text = subtitle
            filtered = clean_subtitle_line(pass_text)
            if(filtered != "" and len(filtered) > 1):
                result = re.sub(r"[-()\"#/@%\\;:<>{}`'+=~|.!?,]", "", str(model.predict(filtered)[0]).split("__label__",1)[1])
                print("\t\tLanguage Detected: " + result + " on " + filtered + "\t")
                if(result == "en" or result == "eng"):
                    total_english += 1
            else:
                print("\t\tEmpty filtered subtitle.")
        except Exception or TypeError:
            send_error_message("Error determining result of subtitle: " + str(subtitle.text))
    return (total_english/total_lines)*100

def parse_subtitle_lines_into_array(input_file):
    extension = os.path.splitext(input_file)[1]
    extension = (re.sub(r"(\.)", "", extension)).strip()
    subtitles = parser.parse(input_file, subtitle_type=extension, encoding=detect_subtitle_encoding(input_file))
    output = []
    for subtitle in subtitles:
        output.append(subtitle)
    return output

def convert_subtitle_file(output_file_with_path):
    if(not str(output_file_with_path).endswith(".srt")):
        if(user_os == "Windows"):
            call = "SubtitleEdit /convert " + "\"\\\\?\\" + output_file_with_path + "\" srt /RemoveFormatting /MergeSameTexts /overwrite"
        elif(user_os == "Linux"):
            call = "xvfb-run -a mono "+path_to_subtitle_edit_linux+"SubtitleEdit.exe /convert " + "\""  + output_file_with_path + "\" srt /RemoveFormatting /MergeSameTexts /overwrite"
        try:
            call = subprocess.run(call, shell=True)
        except subprocess.CalledProcessError as e:
            print(e.output)
        converted_file = os.path.splitext(output_file_with_path)[0] + ".srt"
        if(os.path.isfile(converted_file) and call.returncode == 0):
            print("\t\tConversion successfull.")
            print("\t\tRemoving unconverted file.")
            remove_file(output_file_with_path)
            return converted_file
        else:
            send_error_message("Conversion failed.\n")
        return converted_file
    else:
        return output_file_with_path

def find_files_by_release_group(release_group, files):
    found = []
    for file in files:
        if re.search(release_group, file, flags=re.IGNORECASE):
            found.append(file)
    found.sort()
    return found

def get_mkv_tracks(full_path):
    mkv = pymkv.MKVFile(full_path)
    tracks = mkv.get_track()
    return tracks

def remove_all_tracks_but_subtitles(tracks):
    clean = []
    for track in tracks:
        if(track._track_type == "subtitles"):
            clean.append(track)
    return clean

def remove_signs_and_subs(files, original_file, original_files_results):
    original_files_results = clean_subtitle_lines(original_files_results)
    original_file_releaser = re.search(r"-(?:.(?!-))+$", original_file)
    original_file_releaser = re.sub(r"([-\.])(mkv)", "", original_file_releaser.group())
    original_file_releaser = (re.sub(r"-", "", original_file_releaser)).lower()
    if original_file_releaser != "":
        comparision_releases = find_files_by_release_group(original_file_releaser, files)
        if(len(comparision_releases) != 0):
            comparision_releases.remove(original_file)
            for f in reversed(comparision_releases):
                comparision_full_path = os.path.join(root, f)
                tracks = get_mkv_tracks(comparision_full_path)
                tracks = remove_all_tracks_but_subtitles(tracks)
                for comparision_track in tracks:
                    if(comparision_track._track_type == "subtitles"):
                        extension = set_extension(comparision_track)
                        output_file_with_path = extract_output_subtitle_file_and_convert("lang_comparison"+"."+extension, comparision_track, comparision_full_path)
                        comparision_subtitle_lines_array = parse_subtitle_lines_into_array(output_file_with_path)
                        comparision_subtitle_lines_array = clean_subtitle_lines(comparision_subtitle_lines_array)
                        duplicates_removed = 0
                        removed = []
                        for result in comparision_subtitle_lines_array[:]:
                            if result in original_files_results:
                                original_files_results.remove(result)
                                removed.append(result)
                                duplicates_removed += 1
                        if duplicates_removed > 1:
                            match_result = evaluate_subtitle_lines(original_files_results)
                            set_result = check_and_set_result_two(match_result, full_path, track, "eng", output_file_with_path)
                            if (set_result == 1):
                                return
        else:
            print("\t\tNo similar release found for: " + file + " at " + root)

def clean_and_sort(files, root, dirs):
    remove_hidden_files(files, root)
    dirs[:] = [d for d in dirs if d not in ignored_folders]
    dirs.sort()
    files.sort()
    for file in files[:]:
        fileIsTrailer = str(re.search('trailer', str(file), re.IGNORECASE))
        fileEndsWithMKV = file.endswith(".mkv")
        if(not fileEndsWithMKV or fileIsTrailer != "None"):
            files.remove(file)

def search_track_for_language_keyword(path, track, lang_code):
    if(re.search('english', str(track.track_name), re.IGNORECASE) or re.search(r"\beng\b", str(track.track_name), re.IGNORECASE)):
        print("\t\t" + "English keyword found in track name.")
        print("\t\t" + "Setting track language to english.")
        set_track_language(path, track, lang_code)
        return 1
    else:
        print("\t\t" + "No language keyword found in track name.")
        return 0

# The execution start of the program
if discord_webhook_url != "":
    send_discord_message("[START]-------------------------------------------[START]")
    send_discord_message("Start Time: " + str(datetime.now()))
    send_discord_message("Script: anime_lang_track_corrector.py")
    send_discord_message("Path: " + path)

if os.path.isdir(path):
    os.chdir(path)
    for root, dirs, files, in os.walk(path):
        clean_and_sort(files, root, dirs)
        print("\nCurrent Path: ", root + "\nDirectories: ", dirs)
        print("Files: ", files)
        for file in files:
            full_path = os.path.join(root, file)
            file_without_extension = os.path.splitext(full_path)[0]
            if os.path.isfile(full_path):
                print("\n\tPath: ", root)
                print("\tFile: " + file)
                try:
                    isMKVFile = pymkv.verify_matroska(full_path)
                    if isMKVFile:
                        print("\t" + "isValidMKV: " + str(isMKVFile))
                        isSupportedByMKVMerge = pymkv.verify_supported(full_path)
                        if isSupportedByMKVMerge:
                            print("\t" + "isSupportedByMKVMerge: " + str(isSupportedByMKVMerge))
                            tracks = get_mkv_tracks(full_path) 
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
                                            if(sign != "None"):
                                                print("\t\t" + "Track name contains a Signs keyword.")
                                                if(total_audio_and_subtitle_tracks > 0):
                                                    if((total_audio_and_subtitle_tracks % 2) == 0):
                                                        if(unknown_audio_track_count == 0 and unknown_subtitle_track_count == 1):
                                                            if(total_audio_and_subtitle_tracks - (jpn_audio_track_count + eng_audio_track_count + jpn_subtitle_track_count + eng_subtitle_track_count) == unknown_subtitle_track_count):
                                                                print("\tTrack determined to be english through process of elimination.")
                                                                subprocess.Popen(["mkvpropedit", full_path,"--edit","track:" + str(track.track_id+1),"--set","language=eng"])
                                                                print("\tTrack set to english.")
                                                                send_change_message("Track set to english: " + full_path + " Track: " + str(track.track_id+1))
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
                                                                send_change_message("Track set to english: " + full_path + " Track: " + str(track.track_id+1))
                                                                break
                                            else:
                                                print("\t\t" + "Language could not be determined through process of elimination.")
                                                detect_subs_via_fasttext()
                                    else:
                                        print("\t\tTrack name is empty, TRACK: " + str(track.track_id) + "on " + full_path)
                                        problematic_children.append("Track name is empty, TRACK: " + str(track.track_id) + " on " + full_path)
                                        detect_subs_via_fasttext()
                                #elif(((track._track_type == "subtitles") and track.language == "jpn") and not (re.search('japanese', str(track.track_name), re.IGNORECASE) or re.search(r"\bjpn\b", str(track.track_name), re.IGNORECASE))):
                                    #extension = set_extension(track)
                                    #detect_subs_via_fasttext()
                                else:
                                    print("\t\t" + "No matching track found.\n")
                        else:
                            print("\t" + "isSupportedByMKVMerge: " + str(isSupportedByMKVMerge))
                    else:
                        print("\t" + "isValidMKV: " + str(isMKVFile))
                except KeyError:
                    send_error_message("\t" + "Error with file: " + file)                        
            else:
                send_error_message("\n\tNot a valid file: " + full_path + "\n")
else :
    send_error_message("Invalid Directory: " + path + "\n")

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
