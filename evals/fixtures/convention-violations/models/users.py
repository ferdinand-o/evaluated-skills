"""User-Model mit zwei Konventions-Verstoessen."""
from sqlalchemy import BigInteger, Column, DateTime, String

from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    userEmail = Column(String(50))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
