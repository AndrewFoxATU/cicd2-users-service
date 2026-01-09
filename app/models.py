# users_service/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    permissions: Mapped[str] = mapped_column(String, nullable=False)  # admin/employee+/employee
    password: Mapped[str] = mapped_column(String, nullable=False)
