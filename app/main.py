import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import engine, get_db
from app.models import Base, User
from app.schemas import UserCreate, UserRead, UserUpdate, UserLogin, TokenResponse
from app.auth import (
    TokenUser,
    create_access_token,
    get_current_user,
    hash_password,
    is_bcrypt_hash,
    require_roles,
    verify_password,
)


# ===============================================
#               APP SETUP
# ===============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===============================================
#           HELPER FUNCTIONS
# ===============================================

def commit_or_rollback(db: Session, msg: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=msg)


# ===============================================
#                 HEALTH
# ===============================================

@app.get("/healthy")
def health():
    return {"status": "ok ok"}



# ===============================================
#                 USERS CRUD
# ===============================================

# -----------------------------
# CREATE USER (admin only)
# -----------------------------
@app.post("/api/users", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: TokenUser = Depends(require_roles("admin")),
):
    data = payload.model_dump()
    data["password"] = hash_password(data["password"])
    user = User(**data)
    db.add(user)
    commit_or_rollback(db, "User could not be created")
    db.refresh(user)
    return user


# -----------------------------
# LIST USERS (admin only)
# -----------------------------
@app.get("/api/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _admin: TokenUser = Depends(require_roles("admin")),
):
    stmt = select(User).order_by(User.id)
    return db.execute(stmt).scalars().all()


# -----------------------------
# GET USER BY ID (admin, service, or self)
# -----------------------------
@app.get("/api/users/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: TokenUser = Depends(get_current_user),
):
    if current.role not in ("admin", "service") and current.id != user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# -----------------------------
# LOGIN
# -----------------------------
@app.post("/api/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    stmt = select(User).where(User.name == payload.name)
    user = db.execute(stmt).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid name or password",
        )

    # Upgrade legacy plaintext rows to bcrypt on successful login
    if not is_bcrypt_hash(user.password):
        user.password = hash_password(payload.password)
        db.commit()
        db.refresh(user)

    token = create_access_token(user.id, user.name, user.permissions)
    return TokenResponse(
        access_token=token,
        user=UserRead.model_validate(user),
    )


# -----------------------------
# ME (any authenticated user)
# -----------------------------
@app.get("/api/me", response_model=UserRead)
def me(
    db: Session = Depends(get_db),
    current: TokenUser = Depends(get_current_user),
):
    if current.id is None:
        raise HTTPException(status_code=403, detail="Not a user token")
    user = db.get(User, current.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# -----------------------------
# UPDATE USER (PUT, admin only)
# -----------------------------
@app.put("/api/users/{user_id}", response_model=UserRead)
def update_user_put(
    user_id: int,
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: TokenUser = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump()
    data["password"] = hash_password(data["password"])
    for field, value in data.items():
        setattr(user, field, value)

    commit_or_rollback(db, "Failed to update user")
    db.refresh(user)
    return user


# -----------------------------
# PARTIAL UPDATE (PATCH, admin only)
# -----------------------------
@app.patch("/api/users/{user_id}", response_model=UserRead)
def update_user_patch(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _admin: TokenUser = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password"] = hash_password(update_data["password"])

    for field, value in update_data.items():
        setattr(user, field, value)

    commit_or_rollback(db, "Failed to update user")
    db.refresh(user)
    return user


# -----------------------------
# DELETE USER (admin only)
# -----------------------------
@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: TokenUser = Depends(require_roles("admin")),
) -> Response:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
