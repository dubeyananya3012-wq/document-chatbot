"""
Firebase token verification.

Core isolation principle: user_id ALWAYS comes from the verified Firebase
ID token, never from a request body or query param. Every router that
touches documents depends on get_current_user, not on any client-supplied
user field.
"""
import json
import os
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings

settings = get_settings()

_app_initialized = False


def _ensure_firebase_initialized():
    global _app_initialized
    if not _app_initialized:
        # 1. Try to load from FIREBASE_SERVICE_ACCOUNT_JSON env var first (takes precedence)
        if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
            try:
                cert_info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
                cred = credentials.Certificate(cert_info)
                firebase_admin.initialize_app(cred)
                _app_initialized = True
                return
            except Exception as e:
                # Fallback if parsing fails or invalid json
                import logging
                logging.getLogger("uvicorn").error(f"Failed to initialize Firebase with JSON env string: {e}")

        # 2. Try file path
        if settings.FIREBASE_SERVICE_ACCOUNT_PATH and os.path.exists(settings.FIREBASE_SERVICE_ACCOUNT_PATH):
            try:
                cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
                firebase_admin.initialize_app(cred)
                _app_initialized = True
                return
            except Exception as e:
                import logging
                logging.getLogger("uvicorn").error(f"Failed to initialize Firebase with service account file path: {e}")

        # 3. Fallback to default application credentials or path-less initialization
        try:
            firebase_admin.initialize_app()
            _app_initialized = True
        except Exception as e:
            raise RuntimeError(
                "Failed to initialize Firebase Admin SDK. Please configure FIREBASE_SERVICE_ACCOUNT_JSON "
                "or verify that a valid service account file is placed at FIREBASE_SERVICE_ACCOUNT_PATH."
            ) from e


_ensure_firebase_initialized()

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Verifies the Firebase ID token sent as 'Authorization: Bearer <token>'.
    Returns a dict with at least 'uid' and 'email'. Raises 401 on any
    failure (expired, malformed, revoked).
    """
    token = credentials.credentials
    try:
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )
    return {
        "uid": decoded["uid"],
        "email": decoded.get("email"),
    }
