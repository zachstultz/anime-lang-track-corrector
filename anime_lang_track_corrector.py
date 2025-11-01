#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime

import fasttext
import pymkv
from chardet.universaldetector import UniversalDetector
from discord_webhook import DiscordWebhook
from langcodes import Language, standardize_tag
from pysubparser import parser

from settings import *

# Version of the script
script_version = (1, 0, 1)
script_version_text = "v{}.{}.{}".format(*script_version)

# Script Execution Location
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# FastText Model Location
PRETRAINED_MODEL_PATH = os.path.join(ROOT_DIR, fasttext_model_name)
model = fasttext.load_model(PRETRAINED_MODEL_PATH)

# Subtitle extraction location
subtitle_location = os.path.join("/tmp", "subs_test")

# The location for SE
se_path = os.path.join(ROOT_DIR, "se")

# The path to the anime folder to be scanned recursively.
path = None

# The individual video file to be processed.
file = None

# The optional discord webhook url to be pinged about changes and errors.
discord_webhook_url = ""

# Whether or not the script is running in a docker container
in_docker = False

if ROOT_DIR == "/app":
    in_docker = True

if not in_docker:
    # create the se folder if it doesn't exist
    if not os.path.isdir(se_path):
        try:
            os.mkdir(se_path)
            if os.path.isdir(se_path):
                print(f"\nCreated directory: {se_path}")
            else:
                print(f"\nFailed to create directory: {se_path}")
                exit()
        except OSError as e:
            print(f"\nFailed to create directory: {se_path}")
            print(f"Error: {e}")
            exit()

    se_download_link = "https://github.com/SubtitleEdit/subtitleedit/releases"

    # if the file count isn't bigger than 1, then there's no files in the se folder
    # bigger than one, because github requries a file for the folder to be created
    se_file_count = [name for name in os.listdir(se_path) if not name.startswith(".")]
    if len(se_file_count) <= 1:
        print(f"\nSubtitleEdit not found!")
        print(f"Download it at: {se_download_link}")
        print(f"Place the contents in: {se_path}")
        exit()

    # if subtitle_location does not exist, create it
    if not os.path.isdir(subtitle_location):
        try:
            os.mkdir(subtitle_location)
            if os.path.isdir(subtitle_location):
                print(f"\nCreated directory: {subtitle_location}")
            else:
                print(f"\nFailed to create directory: {subtitle_location}")
                exit()
        except OSError as e:
            print(f"\nFailed to create directory: {subtitle_location}")
            print(f"Error: {e}")
            exit()

# The required percentage that must be met when detecting an individual language with FastText
required_lang_match_percentage = 70

# Used to determine the total execution time at the end
startTime = datetime.now()

# Stuff printed at the end
items_changed = []
errors = []


# Signs & Full keyword arrays, add any keywords you want to be searched for
signs_keywords = ["sign", "music", "song", "s&s"]

print("Run Settings:")
p = argparse.ArgumentParser(
    description="A script that corrects undetermined and not applicable subtitle flags within mkv files for anime."
)
p.add_argument(
    "-p",
    "--path",
    help="The path to the anime folder to be scanned recursively.",
    required=False,
)
p.add_argument(
    "-f", "--file", help="The individual video file to be processed.", required=False
)
p.add_argument(
    "-wh",
    "--webhook",
    help="The optional discord webhook url to be pinged about changes and errors.",
    required=False,
)
p.add_argument(
    "-lmp",
    "--lang-match-percentage",
    help="The percentage of the detected file language required for the language to be set.",
    required=False,
)
p.add_argument(
    "-se",
    "--se_path",
    help="The path to the SubtitleEdit folder.",
    required=False,
)

# parse the arguments
args = p.parse_args()

if args.path is None and args.file is None:
    print("\tNo path or file specified.")
    exit()

if args.path and args.file:
    print("\tBoth path and file specified, please only specify one.")
    exit()
elif args.path:
    path = args.path
elif args.file:
    file = args.file

print(f"\tPath: {path}")
print(f"\tFile: {file}")

if args.webhook:
    discord_webhook_url = args.webhook
print(f"\tWebhook: {discord_webhook_url}")

if args.lang_match_percentage:
    try:
        required_lang_match_percentage = int(args.lang_match_percentage)
    except ValueError:
        print("Invalid language match percentage.")
        exit()

print(f"\tLanguage Match Percentage: {required_lang_match_percentage}%")

if args.se_path:
    if os.path.isdir(args.se_path):
        se_path = args.se_path
    else:
        print(f"Invalid path to SubtitleEdit folder: {args.se_path}")
        exit()
print(f"\tSubtitleEdit Path: {se_path}")


# Removes the file if it exists (used for cleaning up after FastText detection)
def remove_file(file, silent=False):
    if os.path.isfile(file):
        try:
            os.remove(file)
            if not os.path.isfile(file):
                if not silent:
                    print(f"\n\t\tFile removed: {file}")
            else:
                send_message(f"\t\tFailed to remove file: {file}", error=True)
        except OSError as e:
            send_message(
                f"\t\tFailed to remove file: {file}\n\t\tError: {e}", error=True
            )
    else:
        print(f"\t\tFile does not exist before attempting to remove: {file}")


# Detects the encoding of the supplied subtitle file
def detect_sub_encoding(output_file_with_path):
    try:
        with open(output_file_with_path, "rb") as file:
            detector = UniversalDetector()
            for line in file:
                detector.feed(line)
                if detector.done:
                    break
            detector.close()
            encoding = detector.result["encoding"]
    except FileNotFoundError:
        send_message(
            f"File not found: {output_file_with_path}, defaulting to UTF-8", error=True
        )
        encoding = "UTF-8"
    return encoding


# Appends, sends, and prints our change message
def send_message(message, add_to_changed=False, error=False):
    if message:
        if add_to_changed:
            items_changed.append(message)
        if error:
            errors.append(message)
        send_discord_message(message)
        print(message)


# Sends a discord message
def send_discord_message(message):
    if not discord_webhook_url:
        return

    webhook = DiscordWebhook(
        url=discord_webhook_url, content=f"{message}", rate_limit_retry=True
    )
    webhook.execute()


# Prints the information about the given track
def print_track_info(track):
    print(f"\n\t\tTrack: {track.track_id}")
    print(f"\t\tType: {track._track_type}")
    print(f"\t\tName: {track.track_name}")
    print(f"\t\tLanguage: {track.language}")
    print(f"\t\tCodec: {track.track_codec}")

    if track._track_type == "subtitles":
        print(f"\t\tForced: {track.forced_track}")


# Determines and sets the file extension
def set_extension(track):
    codec_map = {
        "SubStationAlpha": "ass",
        "AdvancedSubStationAlpha": "ass",
        "SubRip/SRT": "srt",
        "HDMV PGS": "pgs",
        "VobSub": "sub",
    }
    return codec_map.get(track.track_codec, "")


# Removes hidden files from list, useful for MacOS
def remove_hidden_files(files, root):
    for file in files[:]:
        if file.startswith(".") and os.path.isfile(os.path.join(root, file)):
            files.remove(file)


# execute command with subprocess and return the output
def execute_command(command):
    process = None
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        while True:
            output = process.stdout.readline()
            if output == b"" and process.poll() is not None:
                break
            if output:
                sys.stdout.buffer.write(output)
                sys.stdout.flush()
    except Exception as e:
        send_message(
            f"Error occurred while executing command: {command} \n{e}", error=True
        )
    return process


# Processes the subtitle file by extracting and converting it
def process_subtitle_file(file_name, track, full_path, root):
    outputted_file = os.path.join(root, file_name)
    call = execute_command(
        [
            "mkvextract",
            "tracks",
            full_path,
            f"{track.track_id}:{outputted_file}",
        ]
    )

    if os.path.isfile(outputted_file) and call.returncode == 0:
        print("\t\tExtraction successful.")
        print("\t\tConverting subtitle for detection.")

        basename = os.path.basename(full_path)
        converted = convert_subtitle_file(outputted_file, basename)

        if os.path.isfile(converted):
            return converted
        else:
            print("\t\tConversion failed.")
    else:
        send_message(
            f"Extraction failed: {outputted_file}\nwith {basename}", error=True
        )


# Sets the track language using mkvpropedit
def set_track_language(path, track, language_code):
    track_number = track.track_id + 1

    try:
        execute_command(
            [
                "mkvpropedit",
                path,
                "--edit",
                f"track:{track_number}",
                "--set",
                f"language={language_code}",
            ]
        )
        send_message(
            f"\t\tFile: {path}\n\t\tTrack: {track_number} set to: {language_code}",
            True,
        )
    except Exception as e:
        send_message(f"{e} File: {path}", error=True)


# Checks the match result and sets the track language if above threshold
def check_and_set_result(
    match_result,
    full_path,
    track,
    lang_code,
    original_subtitle_array,
    root,
    tracks,
):
    file = os.path.basename(full_path)
    match_result_percent = f"{match_result}%"

    if match_result >= required_lang_match_percentage:
        send_message(f"\n\t\tFile: {file}\n\t\tMatch: {match_result_percent}")
        print(f"\t\tSubtitle file detected as {lang_code}")
        set_track_language(full_path, track, lang_code)
    else:
        error_message = (
            f"\n\t\tFile: {file}\n\t\tMatch: {match_result_percent}\n\t\t"
            f"Subtitle match below {required_lang_match_percentage}%, no match found.\n"
        )
        send_message(error_message, error=True)
        if match_result >= 10:
            remove_signs_and_subs(
                files,
                file,
                original_subtitle_array,
                tracks,
                root,
                track,
                file,
                full_path,
            )


# Checks the match result and sets the track language if above threshold
def check_and_set_result_two(match_result, full_path, track, lang_code):
    file = os.path.basename(full_path)
    match_result_percent = f"{match_result}%"

    if match_result >= required_lang_match_percentage:
        full_language_keyword = Language.make(
            language=standardize_tag(lang_code)
        ).display_name()
        send_message(f"\n\t\tFile: {file}\n\t\tMatch: {match_result_percent}")
        print(f"\t\tSubtitle file detected as {full_language_keyword}")
        set_track_language(full_path, track, lang_code)
        return 1
    else:
        send_message(
            f"\n\t\tFile: {file}\n\t\tMatch: {match_result_percent}\n\t\tSubtitle match below {required_lang_match_percentage}%, no match found.\n",
            error=True,
        )
        return 0


lang_codes = [
    "eng",
    "jpn",
    "spa",
    "por",
    "fra",
    "deu",
    "ita",
    "kor",
    "pol",
    "rus",
    "swe",
    "tur",
    "vie",
    "ara",
    "heb",
    "cat",
    "ces",
    "dan",
    "ell",
    "fin",
    "hun",
    "ind",
    "nor",
    "nld",
    "ron",
    "slk",
    "slv",
    "srp",
    "ukr",
    "zho",
]


# Performs FastText language detection on the set of tracks/subtitles
def fast_text_detect(track, extension, root, full_path, tracks):
    lang_keyword_search = ""

    if track.track_name:
        for code in lang_codes:
            lang_keyword_search = contains_language_keyword(
                track, code, full_path
            ) or contains_language_keyword(track, code[:-1], full_path)

            if lang_keyword_search:
                break

    if not lang_keyword_search:
        print("\n\t\tNo language keyword found in track name.")
        print("\t\tFile will be extracted and detection will be attempted.")
        print(f"\t\tExtracting test file to {subtitle_location}")

        try:
            output_file_with_path = process_subtitle_file(
                f"lang_test.{extension}", track, full_path, subtitle_location
            )

            if output_file_with_path:
                subtitle_lines_array = parse_subtitles(output_file_with_path)
                match_result = evaluate_subtitle_lines(subtitle_lines_array)

                if len(match_result) >= 2 and match_result[1] != 0:
                    if standardize_tag(track.language) != standardize_tag(
                        match_result[0]
                    ):
                        check_and_set_result(
                            match_result[1],
                            full_path,
                            track,
                            match_result[0],
                            subtitle_lines_array,
                            root,
                            tracks,
                        )
                    else:
                        print("\t\tCorrect language already set.")

        except Exception as e:
            send_message(
                f"Error occurred while processing track {track.track_id}: {e}",
                error=True,
            )
            return
    else:
        return True


# Cleans the subtitle lines for better language detection
def clean_subtitles(lines):
    cleaned_lines = []

    if lines:
        for line in lines:
            if isinstance(line, str):
                text = line
            elif hasattr(line, "text"):
                text = line.text
            else:
                continue

            clean_one = re.sub(r"(^[a-z$&+,:;=?@#|'<>.^*()%!-]*;)", "", text)
            clean_two = re.sub(r"[0-9$&+,:;=?@#|'<>.^*()%!-]", " ", clean_one)
            clean_three = re.sub(r"(\s{2,})", " ", clean_two).strip()  # Excess space

            if re.search(r"^(\w\s){3,}", clean_three):  # EX: 'D b b l l b''
                continue

            if len(clean_three) > 4:
                cleaned_lines.append(clean_three)

    return cleaned_lines


# Evaluates the subtitle lines using a language detection model
def evaluate_subtitle_lines(subtitles):
    cleaned_subtitles = clean_subtitles(subtitles)
    results = []

    if not cleaned_subtitles:
        return "", 0

    for subtitle in cleaned_subtitles:
        try:
            result = model.predict(subtitle)
            result = re.sub(r"__label__", "", result[0][0])
            print(f'\t\tLanguage Detected: {result} on "{subtitle}"\t')
            results.append(result)
        except Exception as e:
            send_message(
                f"Failed to determine result for subtitle:\n\tSubtitle: {subtitle}\n\tError: {e}",
                error=True,
            )

    if not results:
        return "", 0

    language_counts = {result: results.count(result) for result in results}
    highest_lang_result = max(language_counts, key=language_counts.get)
    highest_lang_result_percent = (
        language_counts[highest_lang_result] / len(cleaned_subtitles)
    ) * 100

    return highest_lang_result, highest_lang_result_percent


# Parses the subtitles from the given input file
# and returns them as a list.
def parse_subtitles(input_file):
    extension = os.path.splitext(input_file)[1].strip(".")
    subtitles = parser.parse(
        input_file,
        subtitle_type=extension,
        encoding=detect_sub_encoding(input_file),
    )
    return list(subtitles)


# Converts the subtitle file to SRT format using SubtitleEdit
def convert_subtitle_file(subtitle_file, source_file):
    if subtitle_file.endswith(".srt"):
        return subtitle_file

    processing_options = [
        "srt",
        "/RemoveFormatting",
        "/MergeSameTexts",
        "/overwrite",
    ]

    call = [
        "xvfb-run",
        "-a",
        "mono",
        os.path.join(se_path, "SubtitleEdit.exe"),
        "/convert",
        subtitle_file,
    ]
    call.extend(processing_options)

    try:
        result = execute_command(call)
        converted_file = f"{os.path.splitext(subtitle_file)[0]}.srt"

        if os.path.isfile(converted_file) and result.returncode == 0:
            print("\t\tConversion successful.")
            return converted_file
        else:
            send_message(
                f"Conversion failed on: {subtitle_file} from {source_file}", error=True
            )
    except Exception as e:
        send_message(f"Subprocess error: {e}", error=True)


# Filters files by release group using regex
def find_files_by_release_group(release_group, files):
    return [
        file for file in files if re.search(release_group, file, flags=re.IGNORECASE)
    ]


# Gets the MKV tracks from the specified file
def get_mkv_tracks(full_path):
    mkv = pymkv.MKVFile(full_path)
    tracks = mkv.get_track()
    return tracks


# Removes all non-subtitle tracks from the list
def remove_all_tracks_but_subtitles(tracks):
    clean = [track for track in tracks if track._track_type == "subtitles"]
    return clean


# Prints similar releases found for comparision
def print_similar_releases(comparision_releases):
    if comparision_releases:
        for release in comparision_releases:
            print(f"\t\t{release}")
    else:
        print("\t\tNo comparision releases found.")


# Checks the internal subtitle tracks for comparision
def check_tracks(tracks, comparision_full_path, original_files_results, track):
    send_message("\t\tChecking internal subtitle tracks for a comparision.")

    # The number of pgs subs that can be used for comparision, per file.
    # Since OCR'ing can take a long time, and end up in an endless loop
    # of OCR'ing all the PGS subs in a 24 episode season.
    pgs_limit = 2
    pgs_count = 0

    for comparision_track in tracks:
        if comparision_track._track_type == "subtitles":
            print_track_info(comparision_track)
            if comparision_track.track_codec == "HDMV PGS":
                pgs_count += 1
                if pgs_count > pgs_limit:
                    print("\n\t\tSkipping PGS, limit reached.")
                    continue

            extension = set_extension(comparision_track)
            output_file_with_path = process_subtitle_file(
                f"lang_comparison.{extension}",
                comparision_track,
                comparision_full_path,
                subtitle_location,
            )
            if output_file_with_path is not None:
                comparision_subtitle_lines_array = parse_subtitles(
                    output_file_with_path
                )
                comparision_subtitle_lines_array = clean_subtitles(
                    comparision_subtitle_lines_array
                )
                duplicates_removed = 0
                removed = []
                for result in comparision_subtitle_lines_array[:]:
                    if result in original_files_results:
                        original_files_results.remove(result)
                        print(f"\t\tDuplicate removed from original: {result}")
                        removed.append(result)
                        duplicates_removed += 1
                if duplicates_removed > 1:
                    print("\t\t-- Comparision Attempt --")
                    print(
                        "\t\tEnough duplicates found between original and comparision."
                    )
                    print("\t\tRetesting original with duplicates removed.")
                    match_result = evaluate_subtitle_lines(original_files_results)
                    if len(match_result) >= 2 and match_result[1] != 0:
                        if standardize_tag(match_result[0]) != standardize_tag(
                            track.language
                        ):
                            set_result = check_and_set_result_two(
                                match_result[1],
                                comparision_full_path,
                                track,
                                match_result[0],
                            )
                            print("\t\t-- Comparision Attempt --")
                            if set_result == 1:
                                return True
                else:
                    print("\t\tNot enough duplicates found in track.")
    send_message("\t\tLanguage could not be determined through internal tracks.")
    send_message("\t\tChecking externally...")
    return False


# Removes unwanted characters and subtitles from the original files
def remove_signs_and_subs(
    files, original_file, original_files_results, tracks, root, track, file, full_path
):
    original_files_results = clean_subtitles(original_files_results)
    tracks.remove(track)

    if not check_tracks(
        tracks, os.path.join(root, file), original_files_results, track
    ):
        original_file_releaser = re.search(r"-(?:.(?!-))+$", original_file)
        original_file_releaser = re.sub(
            r"([-\.])(mkv)", "", original_file_releaser.group()
        )
        original_file_releaser = re.sub(r"-", "", original_file_releaser).lower()

        if original_file_releaser:
            comparision_releases = find_files_by_release_group(
                original_file_releaser, files
            )

            if comparision_releases:
                send_discord_message(
                    f"\n\t\t- Checking Similar Releases to [{original_file_releaser}] -"
                )
                comparision_releases.remove(original_file)

                # limit comparision releases to 3
                if len(comparision_releases) > 3:
                    print("\t\tLimiting comparision releases to 3.")
                    comparision_releases = comparision_releases[:3]

                print("\n")
                print_similar_releases(comparision_releases)

                # The number of pgs subs that can be used for comparision, per file.
                # Since OCR'ing can take a long time, and end up in an endless loop
                # of OCR'ing all the PGS subs in a 24 episode season.
                pgs_limit = 4

                try:
                    pgs_count = 0
                    for f in reversed(comparision_releases):
                        print(f"\n\t\tFile: {f}")
                        comparision_full_path = os.path.join(root, f)
                        tracks = get_mkv_tracks(comparision_full_path)
                        tracks = remove_all_tracks_but_subtitles(tracks)

                        print(f"\n\t\t--- Tracks [{len(tracks)}] ---")

                        for comparision_track in tracks:
                            if comparision_track._track_type == "subtitles":
                                print_track_info(comparision_track)

                                if comparision_track.track_codec == "HDMV PGS":
                                    pgs_count += 1
                                    if pgs_count > pgs_limit:
                                        print("\n\t\tSkipping PGS, limit reached.")
                                        continue

                                extension = set_extension(comparision_track)
                                output_file_with_path = process_subtitle_file(
                                    f"lang_comparison.{extension}",
                                    comparision_track,
                                    comparision_full_path,
                                    subtitle_location,
                                )

                                if output_file_with_path:
                                    comparision_subtitle_lines_array = parse_subtitles(
                                        output_file_with_path
                                    )
                                    comparision_subtitle_lines_array = clean_subtitles(
                                        comparision_subtitle_lines_array
                                    )
                                    duplicates_removed = 0
                                    removed = []

                                    for result in comparision_subtitle_lines_array[:]:
                                        if result in original_files_results:
                                            original_files_results.remove(result)
                                            print(
                                                f"\t\tDuplicate removed from original: {result}"
                                            )
                                            removed.append(result)
                                            duplicates_removed += 1

                                    if duplicates_removed > 1:
                                        print("\t\t-- Comparison Attempt --")
                                        print(
                                            "\t\tEnough duplicates found between original and comparison."
                                        )
                                        print(
                                            "\t\tRetesting original with duplicates removed."
                                        )

                                        match_result = evaluate_subtitle_lines(
                                            original_files_results
                                        )

                                        if (
                                            len(match_result) >= 2
                                            and match_result[1] != 0
                                        ):
                                            if standardize_tag(
                                                track.language
                                            ) != standardize_tag(match_result[0]):
                                                set_result = check_and_set_result_two(
                                                    match_result[1],
                                                    full_path,
                                                    track,
                                                    match_result[0],
                                                )
                                                print("\t\t-- Comparison Attempt --")

                                                if set_result == 1:
                                                    return
                                    else:
                                        print(
                                            "\t\tNot enough duplicates found in track."
                                        )

                except Exception as e:
                    send_message(str(e), error=True)
                    return
            else:
                send_message(f"\t\tNo similar release found for: {file} at {root}")
    else:
        send_message("\t\tSuccessfully set through internal subs")


# Cleans and sorts the files and directories
def clean_and_sort(files, root, dirs):
    remove_hidden_files(files, root)

    if len(ignored_folder_names) != 0:
        dirs[:] = [d for d in dirs if d not in ignored_folder_names]

    dirs.sort()
    files.sort()

    for file in files[:]:
        fileIsTrailer = str(re.search("trailer", str(file), re.IGNORECASE))
        fileEndsWithMKV = file.endswith(".mkv")
        if not fileEndsWithMKV or fileIsTrailer != "None":
            files.remove(file)


# Checks if the track name contains a language keyword
def contains_language_keyword(track, lang_code, full_path):
    if not track.track_name:
        return False

    full_language_keyword = Language.make(
        language=standardize_tag(lang_code)
    ).display_name()

    track_name = str(track.track_name)

    if re.search(
        full_language_keyword,
        track_name,
        re.IGNORECASE,
    ) or re.search(rf"\b{lang_code}\b", track_name, re.IGNORECASE):
        if standardize_tag(track.language) != standardize_tag(lang_code):
            send_message(
                f"\t\tFile: {full_path}\n\t\t\t{full_language_keyword} keyword found in track name."
            )
            set_track_language(full_path, track, lang_code)
        else:
            print(
                f"\t\tFile: {full_path}\n\t\t\t{full_language_keyword} keyword found in track name."
            )
            print("\n\t\tCorrect language already set.")
        return True
    return False


# The execution start of the program
if discord_webhook_url != "":
    send_message("")
    send_message("\n[START]-------------------------------------------[START]")
    send_message(f"Start Time: {datetime.now()}")
    send_message("Script: anime_lang_track_corrector.py")
    if path:
        send_message(f"Path: {path}")
    elif file:
        send_message(f"File: {file}")
    else:
        exit()


# Checks if any sign keywords are in the track name
def contains_sign_keyword(track_name):
    for sign in signs_keywords:
        if sign.lower() in track_name.lower():
            return True
    return False


# The main start function that processes files
def start(files, root, dirs):
    clean_subtitle_location()  # clean out the subs_test folder
    for file in files:
        full_path = os.path.join(root, file)
        file_without_extension = os.path.splitext(full_path)[0]

        if os.path.isfile(full_path):
            print(f"\n\tPath: {root}")
            print(f"\tFile: {file}")
            try:
                if file.endswith(".mkv"):
                    tracks = get_mkv_tracks(full_path)
                    track_counts = count_tracks(tracks)
                    print(f"\n\t\t--- Tracks [{len(tracks)}] ---")
                    handle_tracks(tracks, track_counts, root, full_path)
            except Exception as e:
                send_message(f"\tError with file: {file} ERROR: {e}", error=True)
        else:
            send_message(
                f"\n\tNot a valid file (do you have mkvtoolnix installed?): {full_path}\n",
                error=True,
            )
    clean_subtitle_location()  # clean out the subs_test folder


def count_tracks(tracks):
    track_counts = {
        "jpn_audio": 0,
        "eng_audio": 0,
        "jpn_subtitle": 0,
        "eng_subtitle": 0,
        "unknown_audio": 0,
        "unknown_subtitle": 0,
    }
    for track in tracks:
        lang = track.language.lower()

        # Normalize track type to a suffix used in track_counts keys
        if track._track_type == "audio":
            suffix = "audio"
        elif track._track_type == "subtitles":
            suffix = "subtitle"
        else:
            suffix = None

        if suffix:
            if lang in ("jpn", "jp"):
                track_counts[f"jpn_{suffix}"] += 1
            elif lang in ("eng", "en"):
                track_counts[f"eng_{suffix}"] += 1
            else:
                track_counts[f"unknown_{suffix}"] += 1

    return track_counts


# Removes all files from subtitle_location
def clean_subtitle_location():
    if os.path.isdir(subtitle_location):
        files = os.listdir(subtitle_location)
        if files:
            for file in files:
                remove_file(os.path.join(subtitle_location, file), silent=True)


def handle_tracks(tracks, track_counts, root, full_path):
    jpn_audio_count = track_counts["jpn_audio"]
    eng_audio_count = track_counts["eng_audio"]
    jpn_subtitle_count = track_counts["jpn_subtitle"]
    eng_subtitle_count = track_counts["eng_subtitle"]
    unknown_audio_count = track_counts["unknown_audio"]
    unknown_subtitle_count = track_counts["unknown_subtitle"]
    total_tracks = sum(track_counts.values())

    # helps avoid processing too many pgs subs
    subtitle_count = 0
    pgs_count = 0

    for track in tracks:
        # skip if the track_type isn't in the list of track types to check
        if track._track_type not in track_types_to_check:
            continue

        # print info about the track
        print_track_info(track)

        if track._track_type == "subtitles":
            clean_subtitle_location()  # clean out the subs_test folder
            extension = set_extension(track)
            subtitle_count += 1

            if track.track_codec == "HDMV PGS":
                pgs_count += 1

            if track.language not in subtitle_languages_to_check:
                continue

            if str(track.track_name) == "None":
                print(
                    f"\t\tTrack name is empty, TRACK: {track.track_id} on {full_path}"
                )
                continue

            done = False

            print("\n\t\tChecking track...")
            sign = contains_sign_keyword(track.track_name)

            if sign:
                print("\t\tTrack name contains a Signs keyword.")
                if total_tracks > 0 and total_tracks % 2 == 0:
                    if unknown_audio_count == 0 and unknown_subtitle_count == 1:
                        if (
                            total_tracks
                            - (
                                jpn_audio_count
                                + eng_audio_count
                                + jpn_subtitle_count
                                + eng_subtitle_count
                            )
                            == unknown_subtitle_count
                        ):
                            send_message(
                                "\tTrack determined to be English through process of elimination."
                            )
                            set_track_language(full_path, track, "eng")
                            done = True

            elif eng_audio_count == 0:
                print("\t\tNo recognized name track.")
                if jpn_subtitle_count == 0 and jpn_audio_count == 1:
                    if eng_subtitle_count == 0 and eng_audio_count == 0:
                        if unknown_audio_count == 0 and unknown_subtitle_count == 1:
                            if (
                                total_tracks - (jpn_audio_count + jpn_subtitle_count)
                                == unknown_subtitle_count
                            ):
                                send_message(
                                    "\tTrack determined to be English through process of elimination."
                                )
                                set_track_language(full_path, track, "eng")
                                done = True

            if not done:
                print(
                    "\t\tLanguage could not be determined through process of elimination."
                )
                fast_text_detect(track, extension, root, full_path, tracks)

        elif track._track_type == "audio":
            # skip if there are no unknown audio tracks
            if unknown_audio_count == 0:
                continue

            # skip if the language is not in the list of languages to check
            if track.language not in audio_languages_to_check:
                continue

            # skip if the track name is empty, audio correct relies on the track name
            if not track.track_name:
                continue

            lang_keyword_search = False

            # check for language keywords
            # EX: eng or english
            for code in lang_codes:
                lang_keyword_search = contains_language_keyword(
                    track, code, full_path
                ) or contains_language_keyword(track, code[:-1], full_path)

                if lang_keyword_search:
                    # update our counts because any upcoming uknown subtitle tracks
                    # could now be determined through elimination
                    track.language = code
                    unknown_audio_count -= 1
                    if code == "eng":
                        eng_audio_count += 1
                    elif code == "jpn":
                        jpn_audio_count += 1
                    break


# Prints the list section with title and items
def print_list_section(title, items):
    if not items:
        return
    send_message(f"\n\t--- {title} ---")
    for it in items:
        send_message(f"{it}\n")


if __name__ == "__main__":
    if path:
        if os.path.isdir(path):
            os.chdir(path)
            for root, dirs, files in os.walk(path):
                clean_and_sort(files, root, dirs)
                print(f"\nCurrent Path: {root}\nDirectories: {dirs}")
                print(f"Files: {files}")
                start(files, root, dirs)
        else:
            send_message(f"\n\tNot a valid path: {path}\n", error=True)
    elif file:
        send_message(f"\n\tFile: {file}")
        if os.path.isfile(file):
            start([os.path.basename(file)], os.path.dirname(file), [])
        else:
            send_message("\n\tFile does not exist.\n", error=True)

    # Print summary
    print_list_section("Errors", errors)
    print_list_section("Items Changed", items_changed)

    # Print execution time
    execution_time = datetime.now() - startTime
    send_message(f"\nTotal Execution Time: {execution_time}")
    send_message("[END]-------------------------------------------[END]\n")
