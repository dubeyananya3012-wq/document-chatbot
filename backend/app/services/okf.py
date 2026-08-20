"""
OKF (Open Knowledge Format) metadata layer.

Stores a companion metadata record per uploaded document in Firestore,
mapping upload-log fields (filename, uploader, timestamp) to OKF-style
provenance fields, and ingestion quality to an OKF trust tier. The
record includes a rendered markdown+YAML-frontmatter string as a field,
so the "companion markdown file" framing from the PRD is preserved even
though the storage backend is Firestore rather than a local file.

Sequencing fix vs. the earlier reverted attempt: write_okf_metadata()
must only be called AFTER a confirmed successful embed (chunk_count > 0
and the vector-store write has already happened). The previous version
wrote the metadata eagerly, so a failed ingestion could still leave
behind an OKF record claiming success - the two records then disagreed.
Callers must not call this from an exception path or before add_chunks()
has returned successfully.

Trust tier is derived from ingestion signals available at upload time
(chunk count, whether the document needed OCR fallback) since the
grounding score itself is only computed later, per-query, against a
specific question - there's no single grounding score to attach to a
document at ingest time. This tier is a starting proxy, not a claim
about answer quality.

Storage: Firestore collection "okf_metadata", one document per
(user_id, filename), keyed deterministically so a re-upload overwrites
the existing record instead of creating a duplicate. Uses the same
Firebase project/credentials as app.services.upload_log - no new
account or service needed, and this now persists across Render
restarts/deploys the same way the upload log does.
"""
import re
from datetime import datetime, timezone

from firebase_admin import firestore

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = firestore.client()
    return _db


def _safe_slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text)


def _doc_id(user_id: str, filename: str) -> str:
    return f"{_safe_slug(user_id)}__{_safe_slug(filename)}"


def _derive_trust_tier(chunk_count: int, used_ocr: bool) -> str:
    if chunk_count == 0:
        return "unverified"
    if used_ocr:
        # OCR-derived text is more error-prone than native-text extraction
        return "medium"
    return "high"


def _render_markdown(filename: str, user_id: str, timestamp: str, chunk_count: int, trust_tier: str) -> str:
    return f"""---
okf_version: "0.1"
provenance:
  source_filename: "{filename}"
  uploader_id: "{user_id}"
  ingested_at: "{timestamp}"
trust:
  tier: "{trust_tier}"
  chunk_count: {chunk_count}
---

# {filename}

Ingested for user `{user_id}` at {timestamp}. {chunk_count} chunks indexed.
Trust tier: **{trust_tier}** (derived from ingestion signals at upload
time - see module docstring for how this differs from a per-answer
grounding score).
"""


def write_okf_metadata(
    user_id: str,
    filename: str,
    chunk_count: int,
    used_ocr: bool = False,
) -> str:
    """
    Only call this after a confirmed successful embed (chunk_count > 0
    and add_chunks() has already returned). Returns the Firestore
    document ID written.
    """
    trust_tier = _derive_trust_tier(chunk_count, used_ocr)
    timestamp = datetime.now(timezone.utc).isoformat()
    doc_id = _doc_id(user_id, filename)

    _get_db().collection("okf_metadata").document(doc_id).set(
        {
            "filename": filename,
            "uploader_id": user_id,
            "ingested_at": timestamp,
            "trust_tier": trust_tier,
            "chunk_count": chunk_count,
            "used_ocr": used_ocr,
            "markdown": _render_markdown(filename, user_id, timestamp, chunk_count, trust_tier),
        }
    )
    return doc_id


def get_okf_metadata(user_id: str, filename: str) -> dict | None:
    doc = _get_db().collection("okf_metadata").document(_doc_id(user_id, filename)).get()
    return doc.to_dict() if doc.exists else None


def delete_okf_metadata(user_id: str, filename: str) -> None:
    _get_db().collection("okf_metadata").document(_doc_id(user_id, filename)).delete()
