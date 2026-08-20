"""
Upload-time file security.

Three independent checks, all applied before a file ever reaches
Docling or the vector store:

1. sanitize_filename - collapses whatever the client sent down to a
   safe basename. A client-supplied filename is untrusted input; using
   it directly in a filesystem path (as the original version did) is a
   path-traversal risk (e.g. "../../etc/something").
2. write_upload_capped - streams the upload to disk in fixed-size
   chunks and aborts as soon as MAX_UPLOAD_SIZE_MB is exceeded, instead
   of buffering the whole file first. Caps both disk and memory use per
   request regardless of what Content-Length claims.
3. sniff_file_signature - checks the file's actual magic bytes against
   what its extension claims. Extension-only checks (the original
   ALLOWED_EXTENSIONS gate) can be spoofed by renaming an arbitrary
   file - this catches that before it's handed to a parser.
"""
import os
import re

from fastapi import HTTPException, UploadFile

# Magic-byte signatures. docx/pptx/xlsx are all zip containers, so they
# share the same signature - Docling itself determines which of those
# it actually is.
_SIGNATURES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
    ".docx": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
}
_CHUNK_SIZE = 1024 * 1024  # 1 MB read/write chunks


def sanitize_filename(raw_filename: str | None) -> str:
    if not raw_filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # basename() strips any directory component, which is what defeats
    # "../" style traversal regardless of how many levels it tries to climb.
    name = os.path.basename(raw_filename)
    name = name.replace("\x00", "")  # null-byte injection guard
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip()

    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if len(name) > 255:
        base, ext = os.path.splitext(name)
        name = base[: 255 - len(ext)] + ext

    return name


async def write_upload_capped(file: UploadFile, dest_path: str, max_size_mb: int) -> None:
    """
    Streams `file` to `dest_path` in chunks, raising 413 the moment the
    running total exceeds max_size_mb - never buffers the full upload
    in memory and never writes more than the cap to disk.
    """
    max_bytes = max_size_mb * 1024 * 1024
    written = 0

    with open(dest_path, "wb") as out:
        while True:
            chunk = await file.read(_CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                out.close()
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds the {max_size_mb} MB upload limit",
                )
            out.write(chunk)

    if written == 0:
        os.remove(dest_path)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")


def sniff_file_signature(path: str, ext: str) -> bool:
    """
    Returns True if the file's leading bytes match what its extension
    claims. .md/.txt have no reliable magic number, so they're checked
    separately (must decode as UTF-8 text) rather than by signature.
    """
    expected = _SIGNATURES.get(ext)
    if expected is None:
        return True  # no signature defined for this extension - handled elsewhere

    with open(path, "rb") as f:
        header = f.read(8)

    return any(header.startswith(sig) for sig in expected)


def looks_like_text(path: str, sample_bytes: int = 4096) -> bool:
    """For .md/.txt: reject files that don't decode as UTF-8 text,
    which catches an arbitrary binary renamed to a text extension."""
    try:
        with open(path, "rb") as f:
            sample = f.read(sample_bytes)
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False
