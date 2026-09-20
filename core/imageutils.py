import hashlib
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps

THUMB_DIR = 'thumbs'
THUMB_SIZES = {
    'card': (640, 420),
    'gallery': (600, 450),
    'cover': (1280, 720),
}


def _thumb_location(file_field, size):
    digest = hashlib.md5(file_field.name.encode('utf-8')).hexdigest()[:12]
    rel = Path(THUMB_DIR) / f'{digest}_{size[0]}x{size[1]}.jpg'
    return Path(settings.MEDIA_ROOT) / rel, rel


def thumbnail_url(file_field, preset='card'):
    """Return a cached, resized JPEG url for an ImageField, or '' when empty."""
    if not file_field or not file_field.name:
        return ''
    size = THUMB_SIZES.get(preset, THUMB_SIZES['card'])
    abs_path, rel = _thumb_location(file_field, size)
    try:
        if not abs_path.exists():
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(file_field.path) as img:
                img = ImageOps.exif_transpose(img).convert('RGB')
                img.thumbnail(size, Image.LANCZOS)
                img.save(abs_path, 'JPEG', quality=80, optimize=True)
        return f'{settings.MEDIA_URL}{rel.as_posix()}'
    except Exception:
        return file_field.url


def delete_thumbnails(file_field):
    if not file_field or not file_field.name:
        return
    for size in THUMB_SIZES.values():
        abs_path, _ = _thumb_location(file_field, size)
        try:
            abs_path.unlink(missing_ok=True)
        except OSError:
            pass
