import pytest
import os
from litellm_adk.memory.file import FileMemory
from litellm_adk.memory.mongodb import MongoDBMemory
from litellm_adk.memory.sqlalchemy import SQLAlchemyMemory
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_file_memory(tmp_path):
    mem_file = tmp_path / "conversations.json"
    fm = FileMemory(file_path=str(mem_file))
    
    await fm.save_session_metadata("session123", {"user": "Alice"})
    loaded = await fm.get_session_metadata("session123")
    assert loaded["user"] == "Alice"

@patch("motor.motor_asyncio.AsyncIOMotorClient")
@pytest.mark.asyncio
async def test_mongodb_memory(mock_client):
    mock_db = MagicMock()
    mock_coll = MagicMock()
    mock_client.return_value.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_coll
    
    mock_coll.find_one = AsyncMock()
    mock_coll.find_one.return_value = {"_id": "session456", "messages": [], "metadata": {"user": "Bob"}}
    mock_coll.update_one = AsyncMock()
    
    mm = MongoDBMemory(connection_string="mongodb://localhost:27017", database_name="test", collection_name="sessions")
    
    await mm.save_session_metadata("session456", {"user": "Bob"})
    mock_coll.update_one.assert_called_once()
    
    loaded = await mm.get_session_metadata("session456")
    assert loaded["user"] == "Bob"

@patch("litellm_adk.memory.sqlalchemy.create_async_engine")
def test_sqlalchemy_memory(mock_engine):
    # Mock engine and session
    engine_instance = MagicMock()
    mock_engine.return_value = engine_instance
    
    sam = SQLAlchemyMemory("sqlite+aiosqlite:///:memory:")
    
    # We just ensure initialization didn't crash
    assert sam.engine is not None
