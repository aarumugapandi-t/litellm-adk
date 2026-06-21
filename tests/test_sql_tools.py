import pytest
from litellm_adk.tools.sql_tools import SQLTools, DatabaseAccessLevel

@pytest.fixture
def sqlite_url():
    return "sqlite:///:memory:"

def test_sql_tools_read_only(sqlite_url):
    tools = SQLTools(sqlite_url, {"access_level": DatabaseAccessLevel.READ_ONLY})
    
    # Read should not be blocked (it will fail with no such table, but that's fine)
    res = tools.execute_sql_tool("SELECT * FROM users")
    assert "Security Exception" not in res
    assert "Database Error" in res
    
    # Write should be blocked
    res_insert = tools.execute_sql_tool("INSERT INTO users VALUES (2, 'Bob')")
    assert "Security Exception" in res_insert
    
    res_drop = tools.execute_sql_tool("DROP TABLE users")
    assert "Security Exception" in res_drop

def test_sql_tools_read_write(sqlite_url):
    tools = SQLTools(sqlite_url, {"access_level": DatabaseAccessLevel.READ_WRITE})
    
    # Write should NOT be blocked (it will fail with no such table)
    res_insert = tools.execute_sql_tool("INSERT INTO users VALUES (2, 'Bob')")
    assert "Security Exception" not in res_insert
    
    # Schema change should fail
    res_drop = tools.execute_sql_tool("DROP TABLE users")
    assert "Security Exception" in res_drop

def test_sql_tools_admin(sqlite_url):
    tools = SQLTools(sqlite_url, {"access_level": DatabaseAccessLevel.ADMIN})
    
    # Schema change should work (fail with DB error, but no security block)
    res_create = tools.execute_sql_tool("CREATE TABLE dummy (id INTEGER)")
    assert "Security Exception" not in res_create

