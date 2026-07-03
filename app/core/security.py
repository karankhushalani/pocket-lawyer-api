import json

import firebase_admin
from firebase_admin import credentials, auth, storage
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

_firebase_app = None
_firebase_bucket = None


def get_firebase_app():
    global _firebase_app
    if _firebase_app is None:
        try:
            cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
            _firebase_app = firebase_admin.initialize_app(cred)
        except Exception:
            return None
    return _firebase_app


def get_storage_bucket():
    global _firebase_bucket
    if _firebase_bucket is None:
        app = get_firebase_app()
        if app is None:
            return None
        _firebase_bucket = storage.bucket()
    return _firebase_bucket


DEV_MOCK_USER = User(
    id="00000000-0000-0000-0000-000000000001",
    firebase_uid="dev-user",
    email="dev@pocketlawyer.com",
    name="Dev User",
)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if get_firebase_app() is None:
        return {"uid": "dev-user", "email": "dev@pocketlawyer.com", "name": "Dev User"}
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    token = credentials.credentials
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    uid = token_data.get("uid", "")
    if uid == "dev-user":
        return DEV_MOCK_USER
    result = await db.execute(
        select(User).where(User.firebase_uid == uid)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Call /auth/login first.",
        )
    return user
