from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hash.verify(password, stored_hash)


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_password_reset_token(subject: str | int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire, "type": "password_reset"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def read_password_reset_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        return int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        return None
