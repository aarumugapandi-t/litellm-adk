import pytest
from unittest.mock import MagicMock, patch
from litellm_adk.tools.mongo_tools import MongoTools

@pytest.fixture
def mock_mongo():
    with patch('litellm_adk.tools.mongo_tools.MongoClient') as MockClient:
        mock_db = MagicMock()
        mock_client_instance = MockClient.return_value
        mock_client_instance.get_database.return_value = mock_db
        yield mock_db

def test_mongo_aggregation_blocks_out(mock_mongo):
    tools = MongoTools("mongodb://localhost:27017", "test")
    
    # Allowed pipeline
    res_allowed = tools.execute_mongo_aggregate("users", [{"$match": {"status": "active"}}])
    assert "Security Error" not in res_allowed
    
    # Blocked $out pipeline
    res_blocked_out = tools.execute_mongo_aggregate("users", [{"$out": "backup_users"}])
    assert "Security Error" in res_blocked_out
    assert "prohibited" in res_blocked_out

def test_mongo_aggregation_blocks_merge(mock_mongo):
    tools = MongoTools("mongodb://localhost:27017", "test")
    
    # Blocked $merge pipeline
    res_blocked_merge = tools.execute_mongo_aggregate("users", [{"$merge": {"into": "other_users"}}])
    assert "Security Error" in res_blocked_merge
