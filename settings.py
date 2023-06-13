# The linux location for SE
path_to_subtitle_edit_linux = "/PATH/TO/SUBTITLE/EDIT/FOLDER"

# The name of the fasttext model in the root of the script folder
fasttext_model_name = "lid.176.bin"

# Folder names to ignore when recursively scanning a path
ignored_folder_names = ["Serial Experiments Lain (1998) [tvdb-78814]"]

# The list of track languages that will trigger a detection attempt.
track_languages_to_check = [
    "zxx",
    "und",
    # "jpn", # sometimes releasers mark a track as jpn, but they're not actually jpn subtitles
    # "mul" # sometimes a track is set as multi, but it isn't actually multi
]
