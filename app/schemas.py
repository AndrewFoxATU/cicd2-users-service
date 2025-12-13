# users_service/schemas.py
from pydantic import BaseModel
from typing import Optional, Literal

class UserBase(BaseModel):
    name: str
    permissions: Literal["admin", "employee", "employee+"]

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[Literal["admin", "employee", "employee+"]] = None
    password: Optional[str] = None

class UserRead(UserBase):
    id: int

    class Config:
        from_attributes = True
