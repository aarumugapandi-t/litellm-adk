from typing import List, Dict, Any, Optional
from .base import BaseMemory
from ..observability.logger import adk_logger

class MongoDBMemory(BaseMemory):
    """
    Asynchronous MongoDB persistence for conversation history.
    Uses motor for non-blocking I/O.
    """
    def __init__(
        self, 
        connection_string: str = "mongodb://localhost:27017/",
        database_name: str = "litellm_adk",
        collection_name: str = "conversations"
    ):
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            self.client = AsyncIOMotorClient(connection_string)
            self.db = self.client[database_name]
            self.collection = self.db[collection_name]
        except ImportError:
            raise ImportError("Motor not installed. Please run `pip install motor`.")

    async def _ensure_index(self):
        # Lazy index creation
        await self.collection.create_index("session_id", unique=True)

    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        doc = await self.collection.find_one({"session_id": session_id})
        if doc:
            return list(doc.get("messages", []))
        return []

    async def add_message(self, session_id: str, message: Dict[str, Any]):
        await self.collection.update_one(
            {"session_id": session_id},
            {"$push": {"messages": message}},
            upsert=True
        )

    async def add_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        await self.collection.update_one(
            {"session_id": session_id},
            {"$push": {"messages": {"$each": messages}}},
            upsert=True
        )

    async def clear(self, session_id: str):
        await self.collection.update_one(
            {"session_id": session_id},
            {"$set": {"messages": [], "metadata": {}}}
        )

    async def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        doc = await self.collection.find_one({"session_id": session_id})
        if doc:
            return doc.get("metadata", {})
        return {}

    async def save_session_metadata(self, session_id: str, metadata: Dict[str, Any]):
        await self.collection.update_one(
            {"session_id": session_id},
            {"$set": {"metadata": metadata}},
            upsert=True
        )
        
    async def close(self):
        self.client.close()
