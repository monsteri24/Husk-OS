"""Wallpaper paths and aspect-preserving placement, independent of GTK."""
from pathlib import Path

DEFAULT_WALLPAPER = Path('/usr/share/ownos/wallpapers/husk-desert.jpg')
SOURCE_WALLPAPER = Path(__file__).resolve().parents[2] / 'data/wallpapers/husk-desert.jpg'


def wallpaper_candidates(custom=''):
    """A user image may fail to decode; always retain the official fallback."""
    paths = [Path(custom).expanduser()] if custom else []
    return list(dict.fromkeys([*paths, DEFAULT_WALLPAPER, SOURCE_WALLPAPER]))


def image_placement(image_width, image_height, width, height, mode='cover'):
    """Return one uniform scale and centered offset; never stretch the image."""
    if min(image_width, image_height, width, height) <= 0:
        raise ValueError('Image and output dimensions must be positive')
    if mode not in ('cover', 'contain'):
        raise ValueError('Wallpaper mode must be cover or contain')
    choose = max if mode == 'cover' else min
    scale = choose(width / image_width, height / image_height)
    return scale, (width - image_width * scale) / 2, (height - image_height * scale) / 2
