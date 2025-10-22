# The name of the fasttext model in the root of the script folder
fasttext_model_name = "lid.176.ftz"

# Folder names to ignore when recursively scanning a path
ignored_folder_names = []

# The list of track languages that will trigger a detection attempt.
track_types_to_check = [
    "subtitles",
]

# The list of track languages that will trigger a detection attempt.
subtitle_languages_to_check = [
    "zxx",
    "und",
    # "jpn",  # sometimes releasers mark a track as jpn, but they're not actually jpn subtitles
    # "mul" # sometimes a track is set as multi, but it isn't actually multi
]
