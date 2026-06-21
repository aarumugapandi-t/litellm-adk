import pytest
from unittest.mock import patch
from litellm_adk.adapters.sql_adapter import SQLAdapter
from litellm_adk.adapters.mongo_adapter import MongoAdapter

@pytest.fixture
def mock_sql_tools():
    with patch("litellm_adk.adapters.sql_adapter.SQLTools") as mock:
        yield mock

def test_sql_adapter(mock_sql_tools):
    adapter = SQLAdapter({"url": "sqlite:///:memory:"})
    
    mock_instance = mock_sql_tools.return_value
    mock_instance.get_table_names.return_value = ["users"]
    mock_instance.execute_sql_tool.return_value = '[{"id": 1}]'
    
    assert adapter.get_table_names() == ["users"]
    
    tools = adapter.get_tools()
    assert len(tools) == 1
    assert tools[0]("SELECT * FROM users") == '[{"id": 1}]'

@pytest.fixture
def mock_mongo_tools():
    with patch("litellm_adk.adapters.mongo_adapter.MongoTools") as mock:
        yield mock

def test_mongo_adapter(mock_mongo_tools):
    adapter = MongoAdapter({"url": "mongodb://localhost:27017", "database": "testdb"})
    
    mock_instance = mock_mongo_tools.return_value
    mock_instance.get_schema_summary.return_value = '{"users": "schema"}'
    
    assert adapter.get_schema_summary() == '{"users": "schema"}'
    tools = adapter.get_tools()
    assert len(tools) == 2
