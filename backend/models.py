#This file stores information about generated API keys.

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Float
)

from sqlalchemy.sql import func

from .database import Base


# Keep your existing APIKey model.
class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    key_hash = Column(String, unique=True, nullable=False)

    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# NEW MODEL 1: Translation history
class TranslationHistory(Base):
    __tablename__ = "translation_history"

    id = Column(Integer, primary_key=True, index=True)

    api_key_id = Column(
        Integer,
        ForeignKey("api_keys.id"),
        nullable=False,
        index=True
    )

    filename = Column(String, nullable=False)

    document_type = Column(String, nullable=False)

    source_language = Column(String, nullable=True)

    target_language = Column(String, nullable=False)

    file_size = Column(Integer, default=0)

    status = Column(String, default="Pending")

    duration_seconds = Column(Float, nullable=True)

    error_message = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )


# NEW MODEL 2: DeepL usage snapshots
class DeepLUsageSnapshot(Base):
    __tablename__ = "deepl_usage_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    character_count = Column(Integer, default=0)

    character_limit = Column(Integer, default=0)

    document_count = Column(Integer, nullable=True)

    document_limit = Column(Integer, nullable=True)

    captured_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
