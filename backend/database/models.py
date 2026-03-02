# SQLAlchemy ORM models — spec: UI_BUILD_PLAN.md Section 10.

from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    doc_id         = Column(String,          primary_key=True)
    topic          = Column(Text,            nullable=False)
    quality_preset = Column(String(20))
    target_words   = Column(Integer)
    max_budget     = Column(Numeric(10, 4))
    total_cost     = Column(Numeric(10, 6),  default=0)
    total_words    = Column(Integer)
    css_content    = Column(Numeric(4, 3))
    css_style      = Column(Numeric(4, 3))
    css_source     = Column(Numeric(4, 3))
    status         = Column(String(30),      default="initializing")
    created_at     = Column(DateTime,        server_default=func.now())
    completed_at   = Column(DateTime)
    output_paths   = Column(JSONB)
