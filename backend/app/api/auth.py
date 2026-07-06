from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings as app_settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    hash_password,
    read_password_reset_token,
    verify_password,
)
from app.db.session import get_db
from app.db.init_db import seed_demo
from app.models import User, UserSettings
from app.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdate,
    ResetPasswordRequest,
    SettingsRead,
    SettingsUpdate,
    Token,
    UserCreate,
    UserRead,
)
from app.services.notifications import send_password_reset


router = APIRouter()


@router.post("/auth/register", response_model=Token)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=payload.email.lower(), full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id))
    db.commit()
    return Token(access_token=create_access_token(user.id))


@router.post("/auth/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return Token(access_token=create_access_token(user.id))


@router.post("/auth/demo", response_model=Token)
def demo_login(db: Session = Depends(get_db)):
    user = seed_demo(db)
    return Token(access_token=create_access_token(user.id))


@router.post("/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email.lower()).first()
    if user:
        send_password_reset(user, create_password_reset_token(user.id))
    return {"message": "If that email is registered, a reset link is on its way."}


@router.post("/auth/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user_id = read_password_reset_token(payload.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")
    user.password_hash = hash_password(payload.password)
    db.commit()
    return {"message": "Password updated. You can now sign in."}


@router.post("/auth/logout")
def logout():
    return {"ok": True}


@router.get("/auth/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/profile", response_model=UserRead)
def profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/profile", response_model=UserRead)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.email:
        user.email = payload.email.lower()
    if payload.full_name is not None:
        user.full_name = payload.full_name
    db.commit()
    db.refresh(user)
    return user


@router.get("/settings", response_model=SettingsRead)
def settings(user: User = Depends(get_current_user)):
    return user.settings


@router.patch("/settings", response_model=SettingsRead)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user.settings, key, value)
    db.commit()
    db.refresh(user.settings)
    return user.settings


@router.post("/settings/profile-photo", response_model=SettingsRead)
async def update_profile_photo(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
    extension = extensions.get(file.content_type or "")
    if not extension:
        raise HTTPException(status_code=422, detail="Choose a JPG, PNG, WebP, or GIF image")
    contents = await file.read(5 * 1024 * 1024 + 1)
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Profile images must be smaller than 5 MB")
    upload_dir = Path(app_settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"profile-{user.id}-{uuid4().hex}{extension}"
    (upload_dir / filename).write_bytes(contents)
    user.settings.profile_photo_url = str(request.url_for("uploads", path=filename))
    db.commit()
    db.refresh(user.settings)
    return user.settings
