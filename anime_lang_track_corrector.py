import argparse
import os
import platform
import re
import subprocess
from datetime import datetime

import fasttext
import pymkv
from chardet.universaldetector import UniversalDetector
from discord_webhook import DiscordWebhook
from langcodes import *
from pysubparser import parser

from settings import *

# Determine the user's operating system
user_os = platform.system()

# FastText Model Location
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PRETRAINED_MODEL_PATH = os.path.join(ROOT_DIR, fasttext_model_name)
model = fasttext.load_model(PRETRAINED_MODEL_PATH)

# Subtitle extraction location
subtitle_location = os.path.join(ROOT_DIR, "subs_test")

# if subtitle_location does not exist, create it
if not os.path.isdir(subtitle_location):
    try:
        os.mkdir(subtitle_location)
        if os.path.isdir(subtitle_location):
            print("\nCreated directory: " + subtitle_location)
        else:
            print("\nFailed to create directory: " + subtitle_location)
            exit()
    except OSError as e:
        print("\nFailed to create directory: " + subtitle_location)
        print("Error: " + str(e))
        exit()

# The required percentage that must be met when detecting an individual language with FastText
required_lang_match_percentage = 70

# Used to determine the total execution time at the end
startTime = datetime.now()

# Stuff printed at the end
items_changed = []
errors = []


# Signs & Full keyword arrays, add any keywords you want to be searched for
signs_keywords = ["sign", "music", "song"]
full_keywords = ["full", "dialog", "dialogue", "english subs"]

track_languages_to_check = ["zxx", "und"]


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
args = p.parse_args()
# parse the arguments
if args.path:
    path = args.path
else:
    args.path = None
if args.file:
    file = args.file
    path = os.path.dirname(file)
else:
    args.file = None
if args.webhook:
    discord_webhook_url = args.webhook
else:
    discord_webhook_url = ""
if args.lang_match_percentage:
    required_lang_match_percentage = int(args.lang_match_percentage)


# Removes the file if it exists, used for cleaning up after FastText detection
def remove_file(file, silent=False):
    if os.path.isfile(file):
        try:
            os.remove(file)
            if not os.path.isfile(file):
                if not silent:
                    print("\n\t\tFile removed:", file)
            else:
                send_error_message("\t\tFailed to remove file:", file)
        except OSError as e:
            send_error_message(
                "\t\tFailed to remove file:", file, "\n\t\tError:", str(e)
            )
    else:
        print("\t\tFile does not exist before attempting to remove: " + file)


# Detects the encoding of the supplied subtitle file
def detect_subtitle_encoding(output_file_with_path):
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
        send_error_message("File not found: " + output_file_with_path)
        print("Defaulting to UTF-8")
        encoding = "UTF-8"
    return encoding


# Appends, sends, and prints our error message
def send_error_message(message):
    errors.append(message)
    send_discord_message(message)
    print(message)


# Appends, sends, and prints our change message
def send_message(message, add_to_changed=False):
    if message:
        if add_to_changed:
            items_changed.append(message)
        send_discord_message(message)
        print(message)


# Sends a discord message
def send_discord_message(message):
    message = str(message)
    if discord_webhook_url:
        webhook = DiscordWebhook(
            url=discord_webhook_url, content=message, rate_limit_retry=True
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
    if track.track_codec in ["SubStationAlpha", "AdvancedSubStationAlpha"]:
        return "ass"
    elif track.track_codec == "SubRip/SRT":
        return "srt"
    elif track.track_codec == "HDMV PGS":
        return "pgs"
    elif track.track_codec == "VobSub":
        return "sub"
    else:
        return ""


# Removes hidden files from list, useful for MacOS
def remove_hidden_files(files, root):
    for file in files[:]:
        if file.startswith(".") and os.path.isfile(os.path.join(root, file)):
            files.remove(file)


# execute command with subprocess and reutrn the output
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
        send_error_message(str(e))
    return process


def extract_output_subtitle_file_and_convert(file_name, track, full_path, root):
    outputted_file = os.path.join(root, file_name)
    call = execute_command(
        [
            "mkvextract",
            "tracks",
            full_path,
            str(track.track_id) + ":" + outputted_file,
        ]
    )

    if os.path.isfile(outputted_file) and call.returncode == 0:
        print("\t\tExtraction successful.")
        print("\t\tConverting subtitle for detection.")
        converted = convert_subtitle_file(outputted_file, os.path.basename(full_path))

        if converted is not None and os.path.isfile(converted):
            return converted
        else:
            print("\t\tConversion failed.")
    else:
        send_error_message("Extraction failed: " + outputted_file + "\n")


def set_track_language(path, track, language_code):
    try:
        execute_command(
            [
                "mkvpropedit",
                path,
                "--edit",
                "track:" + str(track.track_id + 1),
                "--set",
                "language=" + language_code,
            ]
        )
        send_message(
            f"\t\tFile: {path}\n\t\tTrack: {track.track_id + 1} set to: {language_code}",
            True,
        )
    except Exception as e:
        send_error_message(f"{e} File: {path}")


def check_and_set_result_two(
    match_result, full_path, track, lang_code, output_file_with_path, root, tracks
):
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
        send_error_message(
            f"\n\t\tFile: {file}\n\t\tMatch: {match_result_percent}\n\t\tSubtitle match below {required_lang_match_percentage}%, no match found.\n"
        )
        return 0


def check_and_set_result(
    match_result,
    full_path,
    track,
    lang_code,
    output_file_with_path,
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
        send_error_message(error_message)
        if match_result >= 10:
            remove_signs_and_subs(
                files, file, original_subtitle_array, tracks, root, track, file
            )


lang_codes = [
    "eng",
    "spa",
    "por",
    "fra",
    "deu",
    "ita",
    "jpn",
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


def detect_subs_via_fasttext(track, extension, root, full_path, tracks):
    lang_keyword_search = ""
    lang_keyword_search_short = ""

    if track.track_name:
        for code in lang_codes:
            lang_keyword_search = search_track_for_language_keyword(
                path, track, code, root, full_path
            )
            if lang_keyword_search:
                break

        if not lang_keyword_search:
            for code in lang_codes:
                lang_keyword_search_short = search_track_for_language_keyword(
                    path, track, code[:-1], root, full_path
                )
                if lang_keyword_search_short:
                    break

    if not lang_keyword_search and not lang_keyword_search_short:
        print("\n\t\tNo language keyword found in track name.")
        print("\t\tFile will be extracted and detection will be attempted.")
        print("\t\tExtracting test file to " + subtitle_location)

        try:
            output_file_with_path = extract_output_subtitle_file_and_convert(
                "lang_test." + extension, track, full_path, subtitle_location
            )

            if output_file_with_path:
                subtitle_lines_array = parse_subtitle_lines_into_array(
                    output_file_with_path
                )
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
                            output_file_with_path,
                            subtitle_lines_array,
                            root,
                            tracks,
                        )
                    else:
                        print("\t\tCorrect language already set.")

        except Exception as e:
            send_error_message(str(e))
            return
    else:
        return True


def clean_subtitle_lines(lines):
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
            clean_three = re.sub("(\s{2,})", " ", clean_two).strip()  # Excess space

            if re.search(r"^(\w\s){3,}", clean_three):  # EX: 'D b b l l b''
                continue

            if len(clean_three) > 4:
                cleaned_lines.append(clean_three)

    return cleaned_lines


def evaluate_subtitle_lines(subtitles):
    cleaned_subtitles = clean_subtitle_lines(subtitles)
    results = []

    for subtitle in cleaned_subtitles:
        try:
            result = model.predict(subtitle)
            result = re.sub(r"__label__", "", result[0][0])
            print(f'\t\tLanguage Detected: {result} on "{subtitle}"\t')
            results.append(result)
        except Exception as e:
            send_error_message(
                "Error determining result of subtitle:",
                str(subtitle),
                "\n\t\tError:",
                str(e),
            )

    language_counts = {result: results.count(result) for result in results}
    highest_lang_result = max(language_counts, key=language_counts.get)
    highest_lang_result_percent = (
        language_counts[highest_lang_result] / len(cleaned_subtitles)
    ) * 100

    return highest_lang_result, highest_lang_result_percent


def parse_subtitle_lines_into_array(input_file):
    extension = os.path.splitext(input_file)[1].strip(".")
    subtitles = parser.parse(
        input_file,
        subtitle_type=extension,
        encoding=detect_subtitle_encoding(input_file),
    )
    return list(subtitles)


def convert_subtitle_file(subtitle_file, source_file):
    if subtitle_file.endswith(".srt"):
        return subtitle_file

    processing_options = [
        "srt",
        "/RemoveFormatting",
        "/MergeSameTexts",
        "/overwrite",
    ]

    if user_os == "Windows":
        call = [
            "SubtitleEdit",
            "/convert",
            "\\\\?\\{}".format(subtitle_file),
        ]
        call.extend(processing_options)
        # call = 'SubtitleEdit /convert "\\\\?\\{}" srt /RemoveFormatting /MergeSameTexts /overwrite'.format(
        #     subtitle_file
        # )
    elif user_os == "Linux":
        call = [
            "xvfb-run",
            "-a",
            "mono",
            os.path.join(path_to_subtitle_edit_linux, "SubtitleEdit.exe"),
            "/convert",
            subtitle_file,
        ]
        call.extend(processing_options)

    try:
        result = execute_command(call)
        converted_file = os.path.splitext(subtitle_file)[0] + ".srt"

        if os.path.isfile(converted_file) and result.returncode == 0:
            print("\t\tConversion successful.")
            return converted_file
        else:
            send_error_message(
                f"Conversion failed on: {subtitle_file} from {source_file}"
            )
    except Exception as e:
        print("Subprocess error:", e)


def find_files_by_release_group(release_group, files):
    return [
        file for file in files if re.search(release_group, file, flags=re.IGNORECASE)
    ]


def get_mkv_tracks(full_path):
    mkv = pymkv.MKVFile(full_path)
    tracks = mkv.get_track()
    return tracks


def remove_all_tracks_but_subtitles(tracks):
    clean = [track for track in tracks if track._track_type == "subtitles"]
    return clean


def print_similar_releases(comparision_releases):
    if comparision_releases:
        for release in comparision_releases:
            print("\t\t" + release)
    else:
        print("\t\tNo comparision releases found.")


def check_tracks(tracks, comparision_full_path, original_files_results, root, track):
    send_message("\t\tChecking internal subtitle tracks for a comparision.")
    for comparision_track in tracks:
        if comparision_track._track_type == "subtitles":
            print_track_info(comparision_track)
            extension = set_extension(comparision_track)
            output_file_with_path = extract_output_subtitle_file_and_convert(
                "lang_comparison" + "." + extension,
                comparision_track,
                comparision_full_path,
                subtitle_location,
            )
            if output_file_with_path is not None:
                comparision_subtitle_lines_array = parse_subtitle_lines_into_array(
                    output_file_with_path
                )
                comparision_subtitle_lines_array = clean_subtitle_lines(
                    comparision_subtitle_lines_array
                )
                duplicates_removed = 0
                removed = []
                for result in comparision_subtitle_lines_array[:]:
                    if result in original_files_results:
                        original_files_results.remove(result)
                        print("\t\tDuplicate removed from original: " + result)
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
                                output_file_with_path,
                                root,
                                tracks,
                            )
                            print("\t\t-- Comparision Attempt --")
                            if set_result == 1:
                                return True
                else:
                    print("\t\tNot enough duplicates found in track.")
    send_message("\t\tLanguage could not be determined through internal tracks.")
    send_message("\t\tChecking externally...")
    return False


def remove_signs_and_subs(
    files, original_file, original_files_results, tracks, root, track, file
):
    original_files_results = clean_subtitle_lines(original_files_results)
    tracks.remove(track)

    if not check_tracks(
        tracks, os.path.join(root, file), original_files_results, root, track
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
                    "\n\t\t- Checking Similar Releases to ["
                    + original_file_releaser
                    + "] -"
                )
                comparision_releases.remove(original_file)
                print_similar_releases(comparision_releases)

                try:
                    for f in reversed(comparision_releases):
                        print("\n\t\tFile: " + f)
                        comparision_full_path = os.path.join(root, f)
                        tracks = get_mkv_tracks(comparision_full_path)
                        tracks = remove_all_tracks_but_subtitles(tracks)
                        print("\n\t\t--- Tracks [" + str(len(tracks)) + "] ---")

                        for comparision_track in tracks:
                            if comparision_track._track_type == "subtitles":
                                print_track_info(comparision_track)
                                extension = set_extension(comparision_track)
                                output_file_with_path = (
                                    extract_output_subtitle_file_and_convert(
                                        "lang_comparison" + "." + extension,
                                        comparision_track,
                                        comparision_full_path,
                                        subtitle_location,
                                    )
                                )

                                if output_file_with_path:
                                    comparision_subtitle_lines_array = (
                                        parse_subtitle_lines_into_array(
                                            output_file_with_path
                                        )
                                    )
                                    comparision_subtitle_lines_array = (
                                        clean_subtitle_lines(
                                            comparision_subtitle_lines_array
                                        )
                                    )
                                    duplicates_removed = 0
                                    removed = []

                                    for result in comparision_subtitle_lines_array[:]:
                                        if result in original_files_results:
                                            original_files_results.remove(result)
                                            print(
                                                "\t\tDuplicate removed from original: "
                                                + result
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
                                                    output_file_with_path,
                                                    root,
                                                    tracks,
                                                )
                                                print("\t\t-- Comparison Attempt --")

                                                if set_result == 1:
                                                    return
                                    else:
                                        print(
                                            "\t\tNot enough duplicates found in track."
                                        )

                except Exception as e:
                    send_error_message(str(e))
                    return
            else:
                send_message(
                    "\t\tNo similar release found for: " + file + " at " + root
                )
    else:
        send_message("\t\tSuccessfully set through internal subs")


def clean_and_sort(files, root, dirs):
    remove_hidden_files(files, root)

    if len(ignored_folders) != 0:
        dirs[:] = [d for d in dirs if d not in ignored_folders]

    dirs.sort()
    files.sort()

    for file in files[:]:
        fileIsTrailer = str(re.search("trailer", str(file), re.IGNORECASE))
        fileEndsWithMKV = file.endswith(".mkv")
        if not fileEndsWithMKV or fileIsTrailer != "None":
            files.remove(file)


def search_track_for_language_keyword(path, track, lang_code, root, full_path):
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
                "\t\tFile: "
                + full_path
                + "\n\t\t\t"
                + full_language_keyword
                + " keyword found in track name."
            )
            set_track_language(full_path, track, lang_code)
        else:
            print(
                "\t\tFile: "
                + full_path
                + "\n\t\t\t"
                + full_language_keyword
                + " keyword found in track name."
            )
            print("\t\tCorrect language already set.")
        return True
    return False


# The execution start of the program
if discord_webhook_url != "":
    send_message("")
    send_message("\n[START]-------------------------------------------[START]")
    send_message("Start Time: " + str(datetime.now()))
    send_message("Script: anime_lang_track_corrector.py")
    send_message("Path: " + path)


def check_for_sign_keywords(track_name, track):
    for sign in signs_keywords:
        if re.search(sign, track_name, re.IGNORECASE):
            return True
    return False


def start(files, root, dirs):
    clean_subtitle_location()  # clean out the subs_test folder
    for file in files:
        full_path = os.path.join(root, file)
        file_without_extension = os.path.splitext(full_path)[0]
        if os.path.isfile(full_path):
            print(f"\n\tPath: {root}")
            print(f"\tFile: {file}")
            try:
                is_mkv_file = file.endswith(".mkv")
                # is_mkv_file = pymkv.verify_matroska(full_path)
                if is_mkv_file:
                    # print(f"\tisValidMKV: {is_mkv_file}")
                    is_supported_by_mkvmerge = pymkv.verify_supported(full_path)
                    if is_supported_by_mkvmerge:
                        print(f"\tisSupportedByMKVMerge: {is_supported_by_mkvmerge}")
                        tracks = get_mkv_tracks(full_path)
                        track_counts = count_tracks(tracks)
                        print(f"\n\t\t--- Tracks [{len(tracks)}] ---")
                        handle_tracks(tracks, track_counts, root, full_path)
                    else:
                        print(f"\tisSupportedByMKVMerge: {is_supported_by_mkvmerge}")
                # else:
                #     print(f"\tisValidMKV: {is_mkv_file}")
            except Exception as e:
                send_error_message(f"\tError with file: {file} ERROR: {str(e)}")
        else:
            send_error_message(
                f"\n\tNot a valid file (do you have mkvtoolnix installed?): {full_path}\n"
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
        if track._track_type == "audio":
            if track.language in ["jpn", "jp"]:
                track_counts["jpn_audio"] += 1
            elif track.language in ["eng", "en"]:
                track_counts["eng_audio"] += 1
            else:
                track_counts["unknown_audio"] += 1
        elif track._track_type == "subtitles":
            if track.language in ["jpn", "jp"]:
                track_counts["jpn_subtitle"] += 1
            elif track.language in ["eng", "en"]:
                track_counts["eng_subtitle"] += 1
            else:
                track_counts["unknown_subtitle"] += 1
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

    failed_elimination_text = (
        "Language could not be determined through process of elimination."
    )

    for track in tracks:
        clean_subtitle_location()  # clean out the subs_test folder
        print_track_info(track)

        if track._track_type != "subtitles":
            continue

        extension = set_extension(track)

        if track.language in track_languages_to_check:
            done = False
            print("\n\t\tChecking track...")
            if str(track.track_name) != "None":
                sign = check_for_sign_keywords(track.track_name, track)

                if sign != "None":
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
                                    total_tracks
                                    - (jpn_audio_count + jpn_subtitle_count)
                                    == unknown_subtitle_count
                                ):
                                    send_message(
                                        "\tTrack determined to be English through process of elimination."
                                    )
                                    set_track_language(full_path, track, "eng")
                                    done = True
            else:
                print(
                    f"\t\tTrack name is empty, TRACK: {str(track.track_id)} on {full_path}"
                )
                errors.append(
                    f"Track name is empty, TRACK: {str(track.track_id)} on {full_path}"
                )

            if not done:
                print(f"\t\t{failed_elimination_text}")
                detect_subs_via_fasttext(track, extension, root, full_path, tracks)

        else:
            print("\n\t\tNo matching track found.\n")


if __name__ == "__main__":
    if args.path and args.file:
        send_error_message("\n\tCannot use both --path and --file at the same time.\n")
    elif args.path:
        if os.path.isdir(path):
            os.chdir(path)
            for root, dirs, files in os.walk(path):
                clean_and_sort(files, root, dirs)
                print("\nCurrent Path: ", root + "\nDirectories: ", dirs)
                print("Files: ", files)
                start(files, root, dirs)
        else:
            send_error_message("\n\tNot a valid path: " + path + "\n")
    elif args.file:
        send_message("\n\tFile: " + args.file)
        if os.path.isfile(file):
            start([os.path.basename(file)], os.path.dirname(file), [])
        else:
            send_error_message("\n\tFile does not exist.\n")

    # Print errors
    if errors:
        send_message("\n\t--- Errors ---")
        for problem in errors:
            send_message(str(problem) + "\n")

    # Print items changed
    if items_changed:
        send_message("\n\t--- Items Changed ---")
        for item in items_changed:
            send_message(str(item) + "\n")


    # Print execution time
    execution_time = datetime.now() - startTime
    send_message("\nTotal Execution Time: " + str(execution_time))
    send_message("[END]-------------------------------------------[END]\n")
