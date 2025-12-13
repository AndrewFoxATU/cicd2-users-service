from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import engine, get_db
from app.models import Base, User
from app.schemas import UserCreate, UserRead, UserUpdate, UserLogin


# ===============================================
#               APP SETUP
# ===============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

@app.get("/health")
def health():
    return {"status": "ok"}

# -----------------------------
# LOGIN
# -----------------------------
@app.post("/api/login", response_model=UserRead)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    stmt = select(User).where(User.name == payload.name)
    user = db.execute(stmt).scalar_one_or_none()

    if not user or user.password != payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    return user

# ===============================================
#                 USERS CRUD
# ===============================================

# -----------------------------
# CREATE USER
# -----------------------------
@app.post("/api/users", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = User(**payload.model_dump())
    db.add(user)
    commit_or_rollback(db, "User could not be created")
    db.refresh(user)
    return user


# -----------------------------
# LIST USERS
# -----------------------------
@app.get("/api/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.id)
    return db.execute(stmt).scalars().all()


# -----------------------------
# GET USER BY ID
# -----------------------------
@app.get("/api/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# -----------------------------
# UPDATE USER (PUT)
# -----------------------------
@app.put("/api/users/{user_id}", response_model=UserRead)
def update_user_put(
    user_id: int,
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for field, value in payload.model_dump().items():
        setattr(user, field, value)

    commit_or_rollback(db, "Failed to update user")
    db.refresh(user)
    return user


# -----------------------------
# PARTIAL UPDATE (PATCH)
# -----------------------------
@app.patch("/api/users/{user_id}", response_model=UserRead)
def update_user_patch(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    commit_or_rollback(db, "Failed to update user")
    db.refresh(user)
    return user


# -----------------------------
# DELETE USER
# -----------------------------
@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db)) -> Response:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
