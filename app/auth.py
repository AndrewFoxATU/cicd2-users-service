# users_service/auth.py
# Password hashing + JWT issuing/verification shared by all endpoints.
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Roles a human user can hold; "service" is reserved for service-to-service tokens.
USER_ROLES = ("admin", "employee+", "employee")


class TokenUser(BaseModel):
    id: Optional[int] = None  # None for service tokens
    name: str
    role: str


# -----------------------------
# Password hashing
# -----------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def is_bcrypt_hash(value: str) -> bool:
    return value.startswith(("$2a$", "$2b$", "$2y$"))


def verify_password(password: str, stored: str) -> bool:
    """Verify against a bcrypt hash, or (legacy) a plaintext value from
    before hashing was introduced. Legacy rows are re-hashed on login."""
    if is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False
    return hmac.compare_digest(stored.encode("utf-8"), password.encode("utf-8"))


# -----------------------------
# JWT
# -----------------------------

def create_access_token(
    user_id: Optional[int],
    name: str,
    role: str,
    expires_minutes: Optional[int] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id) if user_id is not None else name,
        "user_id": user_id,
        "name": name,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> TokenUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenUser(
        id=payload.get("user_id"),
        name=payload.get("name", ""),
        role=payload.get("role", ""),
    )


def require_roles(*roles: str):
    def dependency(user: TokenUser = Depends(get_current_user)) -> TokenUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency
