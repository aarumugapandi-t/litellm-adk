import json
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, Text, JSON, DateTime, select, update, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from datetime import datetime
from .base import BaseMemory
from ..observability.logger import adk_logger

Base = declarative_base()

class ConversationModel(Base):  # type: ignore
    __tablename__ = "adk_conversations"
    
    session_id = Column(String(255), primary_key=True)
    messages = Column(JSON, default=list)
    metadata_json = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SQLAlchemyMemory(BaseMemory):
    """
    Production-grade SQLAlchemy (Async) persistence for SQLite, Postgres, etc.
    """
    def __init__(self, connection_url: str = "sqlite+aiosqlite:///adk_memory.db"):
        self.engine = create_async_engine(connection_url)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)
        self._initialized = False

    async def _ensure_db(self):
        if not self._initialized:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            self._initialized = True

    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        await self._ensure_db()
        async with self.async_session() as session:
            result = await session.execute(select(ConversationModel).where(ConversationModel.session_id == session_id))
            conv = result.scalar_one_or_none()
            return conv.messages if conv else []  # type: ignore

    async def add_message(self, session_id: str, message: Dict[str, Any]):
        await self._ensure_db()
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(select(ConversationModel).where(ConversationModel.session_id == session_id))
                conv = result.scalar_one_or_none()
                if conv:
                    # SQLAlchemy mutable JSON tracking can be tricky, so we re-assign
                    updated_messages = list(conv.messages) + [message]
                    conv.messages = updated_messages  # type: ignore
                else:
                    conv = ConversationModel(session_id=session_id, messages=[message])
                    session.add(conv)

    async def add_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        await self._ensure_db()
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(select(ConversationModel).where(ConversationModel.session_id == session_id))
                conv = result.scalar_one_or_none()
                if conv:
                    updated_messages = list(conv.messages) + messages
                    conv.messages = updated_messages  # type: ignore
                else:
                    conv = ConversationModel(session_id=session_id, messages=messages)
                    session.add(conv)

    async def clear(self, session_id: str):
        await self._ensure_db()
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(delete(ConversationModel).where(ConversationModel.session_id == session_id))

    async def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        await self._ensure_db()
        async with self.async_session() as session:
            result = await session.execute(select(ConversationModel).where(ConversationModel.session_id == session_id))
            conv = result.scalar_one_or_none()
            return conv.metadata_json if conv else {}  # type: ignore

    async def save_session_metadata(self, session_id: str, metadata: Dict[str, Any]):
        await self._ensure_db()
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(select(ConversationModel).where(ConversationModel.session_id == session_id))
                conv = result.scalar_one_or_none()
                if conv:
                    conv.metadata_json = metadata  # type: ignore
                else:
                    conv = ConversationModel(session_id=session_id, metadata_json=metadata)
                    session.add(conv)

    async def close(self):
        await self.engine.dispose()
