import os
from pathlib import Path


def get_download_path(fallback_dir: str) -> str:
    """Get base path for YouTube2Audio app"""
    music_dir = os.path.join(Path.home(), "Music")

    if os.path.isdir(music_dir):
        y2a_dir = os.path.join(music_dir, "YouTube2Audio")

        if not os.path.isdir(y2a_dir):
            try:
                os.mkdir(y2a_dir)
            except FileNotFoundError:
                return fallback_dir

        return y2a_dir

    return fallback_dir
