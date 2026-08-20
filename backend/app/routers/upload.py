import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.auth import get_current_user
from app.config import get_settings
from app.models import UploadResponse, UploadHistoryEntry
from app.rate_limit import limiter
from app.services import upload_log
from app.services.chunker import chunk_text
from app.services.docling_loader import parse_document
from app.services.file_security import (
    looks_like_text,
    sanitize_filename,
    sniff_file_signature,
    write_upload_capped,
)
from app.services.okf import delete_okf_metadata, write_okf_metadata
from app.services.pii import redact_pii
from app.services.vectorstore import add_chunks, delete_user_document

router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger("upload")
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


@router.post("", response_model=UploadResponse)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_document(
    request: Request,  # required by slowapi's limiter to read the client key
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    filename = sanitize_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        upload_log.record_upload(filename, user["uid"], 0, "failed", "Unsupported file type")
        return UploadResponse(filename=filename, status="failed", chunk_count=0, error="Unsupported file type")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = os.path.join(tmp_dir, filename)

        # Streams to disk in capped chunks - raises 413 if the file
        # exceeds MAX_UPLOAD_SIZE_MB before it's ever fully written.
        await write_upload_capped(file, tmp_path, settings.MAX_UPLOAD_SIZE_MB)

        # Content-sniffing: catches an arbitrary file renamed to a
        # trusted extension, which ALLOWED_EXTENSIONS alone can't.
        content_ok = (
            sniff_file_signature(tmp_path, ext)
            if ext in {".pdf", ".docx"}
            else looks_like_text(tmp_path)
        )
        if not content_ok:
            upload_log.record_upload(filename, user["uid"], 0, "failed", "File content did not match its extension")
            return UploadResponse(
                filename=filename, status="failed", chunk_count=0,
                error="File content did not match its extension",
            )

        try:
            # Re-upload semantics: replace, not duplicate. If this filename
            # already has chunks for this user, clear them first so a
            # re-upload doesn't leave stale + fresh chunks both queryable.
            delete_user_document(user["uid"], filename)

            parsed = parse_document(tmp_path, filename)

            all_chunks: list[str] = []
            page_numbers: list[int | None] = []
            for page in parsed.pages:
                page_text = redact_pii(page.text) if settings.ENABLE_PII_REDACTION else page.text
                page_chunks = chunk_text(page_text)
                all_chunks.extend(page_chunks)
                page_numbers.extend([page.page_number] * len(page_chunks))

            chunk_count = add_chunks(
                user_id=user["uid"],
                filename=filename,
                chunks=all_chunks,
                page_numbers=page_numbers,
            )

            upload_log.record_upload(filename, user["uid"], chunk_count, "success")

            # OKF metadata write happens LAST, only after the embed and the
            # upload-log record have both already succeeded. If this write
            # fails, it's logged and swallowed rather than raised - a
            # failure here must never roll back or contradict the
            # already-confirmed successful ingestion above (that was the
            # bug in the earlier reverted attempt).
            if chunk_count > 0:
                try:
                    write_okf_metadata(
                        user_id=user["uid"],
                        filename=filename,
                        chunk_count=chunk_count,
                        used_ocr=parsed.used_ocr,
                    )
                except Exception:  # noqa: BLE001 - OKF write failure must not affect the response
                    logger.exception("OKF metadata write failed for %s", filename)

            return UploadResponse(filename=filename, status="success", chunk_count=chunk_count)

        except Exception:
            # Full detail goes to server logs only - the client gets a
            # generic message so internal paths/library errors are never
            # exposed in an HTTP response.
            logger.exception("Upload processing failed for %s (user %s)", filename, user["uid"])
            upload_log.record_upload(filename, user["uid"], 0, "failed", "Processing error")
            return UploadResponse(
                filename=filename, status="failed", chunk_count=0,
                error="We couldn't process this file. Please try a different file.",
            )


@router.get("/history", response_model=list[UploadHistoryEntry])
async def upload_history(user: dict = Depends(get_current_user)):
    return upload_log.get_history_for_user(user["uid"])


@router.get("/documents")
async def list_current_documents(user: dict = Depends(get_current_user)):
    """Currently-live documents for this user - what the UI shows to delete/re-upload against."""
    return upload_log.get_current_documents(user["uid"])


@router.delete("/{filename}")
async def delete_document(filename: str, user: dict = Depends(get_current_user)):
    filename = sanitize_filename(filename)
    history = upload_log.get_history_for_user(user["uid"])
    if not any(e["filename"] == filename and e["status"] == "success" for e in history):
        raise HTTPException(status_code=404, detail="Document not found for this user")

    delete_user_document(user["uid"], filename)
    delete_okf_metadata(user["uid"], filename)
    upload_log.record_deletion(filename, user["uid"])
    return {"filename": filename, "status": "deleted"}
