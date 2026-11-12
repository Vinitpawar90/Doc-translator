#This file stores information about generated API keys.

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    LargeBinary,
    Text
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


class FrontendTranslationHistory(Base):
    __tablename__ = "frontend_translation_history"

    id = Column(String(32), primary_key=True)

    browser_id = Column(String(32), nullable=False, index=True)

    kind = Column(String(20), nullable=False)

    title = Column(String(255), nullable=False)

    source_language = Column(String(32), nullable=False)

    source_language_name = Column(String(100), nullable=False)

    target_language = Column(String(32), nullable=False)

    target_language_name = Column(String(100), nullable=False)

    source_text = Column(Text, nullable=True)

    translated_text = Column(Text, nullable=True)

    translated_data = Column(LargeBinary, nullable=True)

    download_name = Column(String(255), nullable=False)

    mime_type = Column(String(100), nullable=True)

    created_at = Column(Float, nullable=False, index=True)


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, index=True)

    rating = Column(Integer, nullable=False)

    comment = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )


class FeedbackMessage(Base):
    __tablename__ = "feedback_messages"

    id = Column(Integer, primary_key=True, index=True)

    message = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )


class FeedbackAttachment(Base):
    __tablename__ = "feedback_attachments"

    id = Column(Integer, primary_key=True, index=True)

    feedback_id = Column(
        Integer,
        ForeignKey("feedback_messages.id"),
        nullable=False,
        index=True
    )

    content_type = Column(String(100), nullable=False)

    data = Column(LargeBinary, nullable=False)
