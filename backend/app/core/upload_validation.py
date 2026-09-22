from io import BytesIO
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError


def validate_upload(kind: str, body: bytes, mime: str) -> None:
    if not body:
        raise HTTPException(400, "The file is empty.")
    if mime.startswith("image/"):
        try:
            with Image.open(BytesIO(body)) as image:
                if image.width * image.height > 40_000_000:
                    raise HTTPException(400, "Image dimensions are too large.")
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(400, "The file is not a valid image.") from None
    if kind == "customFont" and body[:4] not in (b"wOFF", b"wOF2", b"OTTO", b"\x00\x01\x00\x00"):
        raise HTTPException(400, "Use a valid WOFF, WOFF2, TTF or OTF font.")
    if kind == "clickSound":
        valid = body.startswith((b"ID3", b"OggS", b"fLaC")) or (body[:4] == b"RIFF" and body[8:12] == b"WAVE") or body[4:8] == b"ftyp" or (len(body) > 1 and body[0] == 255 and body[1] & 224 == 224)
        if not valid:
            raise HTTPException(400, "Use a valid MP3, WAV, OGG, FLAC or M4A audio file.")
