"""
Upload history / audit log, backed by Firestore.

Replaces the earlier local-JSON-file version, which did not persist
across deploys/restarts on Render's ephemeral filesystem. Firestore is
free-tier and already available alongside Firebase Auth in the same
project, so no new account/service is needed.

Collection layout: "upload_log" documents, one per upload event
(including deletions), each with uploader/filename/timestamp/status.
This is an append-only event log, not a "current state" table - the
document's current status is derived by reading events in order.
"""
from datetime import datetime, timezone

from firebase_admin import firestore

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = firestore.client()
    return _db


def record_upload(
    filename: str,
    uploader: str,
    chunk_count: int,
    status: str,
    error: str | None = None,
) -> None:
    _get_db().collection("upload_log").add(
        {
            "filename": filename,
            "uploader": uploader,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chunk_count": chunk_count,
            "status": status,
            "error": error,
            "event": "upload",
        }
    )


def record_deletion(filename: str, uploader: str) -> None:
    _get_db().collection("upload_log").add(
        {
            "filename": filename,
            "uploader": uploader,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chunk_count": 0,
            "status": "deleted",
            "error": None,
            "event": "delete",
        }
    )


def get_history_for_user(uploader: str) -> list[dict]:
    """Full raw event history (uploads + deletions), newest first."""
    docs = (
        _get_db()
        .collection("upload_log")
        .where("uploader", "==", uploader)
        .stream()
    )
    results = [d.to_dict() for d in docs]
    # Sort in memory by timestamp descending
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results


def get_current_documents(uploader: str) -> list[dict]:
    """
    Derives the user's currently-live document list from the event log:
    for each filename, the most recent event determines whether it's
    live. A later "delete" event removes it even if an earlier
    "upload" event for the same filename succeeded.
    """
    events = get_history_for_user(uploader)  # newest first
    latest_by_filename: dict[str, dict] = {}
    for e in events:
        if e["filename"] not in latest_by_filename:
            latest_by_filename[e["filename"]] = e

    return [
        e for e in latest_by_filename.values()
        if e["event"] == "upload" and e["status"] == "success"
    ]
