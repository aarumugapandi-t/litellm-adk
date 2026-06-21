import pytest
import tempfile
import os
from litellm_adk.approval import SQLiteApprovalManager
from litellm_adk.models import ApprovalStatus

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass

def test_sqlite_approval_manager(temp_db):
    manager = SQLiteApprovalManager(db_path=temp_db)
    manager._init_db()
    
    # Create request
    manager.create_request("call_1", "session_1", "tool_name", {"arg": "val"})
    req = manager.get_request("call_1")
    assert req.status == ApprovalStatus.PENDING
    
    # Approve request
    manager.submit_decision("call_1", ApprovalStatus.APPROVED, "human", "looks good")
    req_updated = manager.get_request("call_1")
    assert req_updated.status == ApprovalStatus.APPROVED
    assert req_updated.reviewer == "human"
    assert req_updated.reason == "looks good"

def test_sqlite_approval_manager_missing(temp_db):
    manager = SQLiteApprovalManager(db_path=temp_db)
    manager._init_db()
    assert manager.get_request("non_existent") is None
