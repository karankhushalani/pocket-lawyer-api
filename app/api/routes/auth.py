from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    name: str
    email: str


@router.post("/register")
async def register(
    body: RegisterBody,
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    firebase_uid = token_data["uid"]
    existing = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = User(firebase_uid=firebase_uid, email=body.email, name=body.name)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"user_id": str(user.id), "email": user.email, "name": user.name}


@router.post("/login")
async def login(
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    firebase_uid = token_data["uid"]
    email = token_data.get("email", "")
    name = token_data.get("name", "")

    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(firebase_uid=firebase_uid, email=email, name=name)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return {
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
    }


@router.get("/me")
async def get_me(
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    firebase_uid = token_data["uid"]
    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
    }
