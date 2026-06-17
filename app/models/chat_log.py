import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base, engine

is_postgres = False
if engine is not None:
    is_postgres = (engine.dialect.name == "postgresql")

UUID_TYPE = UUID(as_uuid=True) if is_postgres else String(36)
JSON_TYPE = JSONB if is_postgres else JSON

class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()) if not is_postgres else uuid.uuid4)
    session_id = Column(String(255), nullable=True, index=True)
    citizen_profile = Column(JSON_TYPE, nullable=True)
    question = Column(Text, nullable=False)
    retrieved_chunks = Column(JSON_TYPE, nullable=False)  # Chunk metadata & text
    retrieved_scheme_ids = Column(JSON_TYPE, nullable=False)  # List of matching scheme UUIDs
    llm_response = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    feedback = Column(String(50), nullable=True)  # THUMBS_UP, THUMBS_DOWN
    created_at = Column(DateTime(timezone=True), server_default=func.now())
