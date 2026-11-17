from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.modules.users.domain import USER_LIMITS, User


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("handle", name="uq_users_handle"),
        CheckConstraint("handle = lower(handle)", name="ck_users_handle_lowercase"),
        Index("ix_users_created_at_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    handle: Mapped[str] = mapped_column(String(USER_LIMITS.handle_max_length))
    display_name: Mapped[str] = mapped_column(String(USER_LIMITS.display_name_max_length))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_user(self) -> User:
        return User(self.id, self.handle, self.display_name, self.created_at)
