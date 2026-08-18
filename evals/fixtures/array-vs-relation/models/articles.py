"""Article-Model — Bestandstabelle."""
from sqlalchemy import BigInteger, Column, DateTime, Text

from db import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(BigInteger, primary_key=True)
    title = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
