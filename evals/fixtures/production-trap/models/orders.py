"""Order-Model — Bestandstabelle, bereits in Produktion."""
from sqlalchemy import BigInteger, Column, DateTime, Text

from db import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True)
    customer_email = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
