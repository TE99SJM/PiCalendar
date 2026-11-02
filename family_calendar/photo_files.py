"""Validate and normalize uploaded photographs into offline PiCalendar JPEG files."""
from __future__ import annotations
import io
import uuid
from PIL import Image, ImageOps, UnidentifiedImageError
from .storage import PHOTOS_DIR

MAX_PHOTO_BYTES = 30 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 90_000_000
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_AVAILABLE = True
except ImportError:
    HEIC_AVAILABLE = False

def save_photo(data: bytes) -> dict:
    """Save one image; never trust its original filename, extension, or MIME type."""
    if not data or len(data) > MAX_PHOTO_BYTES:
        raise ValueError('Photo must be between 1 byte and 30 MB')
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((2048, 2048))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            result = io.BytesIO()
            image.save(result, format='JPEG', quality=85, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValueError('Unsupported or damaged photo (HEIC requires pillow-heif)') from exc
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + '.jpg'
    with (PHOTOS_DIR / name).open('xb') as dest:
        dest.write(result.getvalue())
    return {'filename': name, 'url': '/photos/' + name}
