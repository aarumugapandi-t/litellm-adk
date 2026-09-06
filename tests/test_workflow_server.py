"""Integration tests for the LiteLLM ADK Workflow Platform FastAPI server."""

import pytest
from fastapi.testclient import TestClient
from litellm_adk.server.app import app
from litellm_adk.persistence.sqlite_workflow import workflow_store


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    import asyncio
    asyncio.run(workflow_store.init_db())


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_spa_serving(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "LiteLLM ADK" in resp.text
    assert "root" in resp.text



def test_node_discovery(client):
    resp = client.get("/api/v1/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    assert isinstance(nodes, list)
    types = [n["type"] for n in nodes]
    assert "manual_trigger" in types
    assert "agent" in types
    assert "llm" in types
    assert "condition" in types
    assert "human" in types
    assert "output" in types


def test_workflow_crud_and_lifecycle(client):
    wf_payload = {
        "id": "crud_test_wf",
        "name": "CRUD Test Workflow",
        "description": "Integration test workflow",
        "active": False,
        "nodes": [
            {"id": "t1", "type": "manual_trigger", "name": "Start", "config": {}},
            {"id": "o1", "type": "output", "name": "End", "config": {"response": "Success"}}
        ],
        "edges": [
            {"id": "e1", "source": "t1", "target": "o1"}
        ]
    }

    # 1. Create
    resp = client.post("/api/v1/workflows", json=wf_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"

    # 2. Get
    resp = client.get("/api/v1/workflows/crud_test_wf")
    assert resp.status_code == 200
    assert resp.json()["name"] == "CRUD Test Workflow"

    # 3. Update
    wf_payload["name"] = "Updated CRUD Workflow"
    resp = client.put("/api/v1/workflows/crud_test_wf", json=wf_payload)
    assert resp.status_code == 200
    assert resp.json()["workflow"]["name"] == "Updated CRUD Workflow"

    # 4. Activate
    resp = client.post("/api/v1/workflows/crud_test_wf/activate")
    assert resp.status_code == 200
    assert resp.json()["active"] is True

    # 5. Duplicate
    resp = client.post("/api/v1/workflows/crud_test_wf/duplicate")
    assert resp.status_code == 200
    dup_id = resp.json()["workflow"]["id"]
    assert dup_id != "crud_test_wf"

    # 6. Execute (Synchronous)
    exec_resp = client.post(
        "/api/v1/workflows/crud_test_wf/execute",
        json={"trigger_data": {"user": "tester"}, "run_async": False}
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["status"] == "completed"
    assert exec_data["outputs"]["o1"] == "Success"

    # 7. Check Executions List
    list_resp = client.get("/api/v1/executions?workflow_id=crud_test_wf")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 8. Export and Import
    exp_resp = client.get("/api/v1/workflows/crud_test_wf/export")
    assert exp_resp.status_code == 200
    exported_data = exp_resp.json()
    exported_data["id"] = "imported_wf_test"
    imp_resp = client.post("/api/v1/workflows/import", json=exported_data)
    assert imp_resp.status_code == 200

    # 9. Delete
    del_resp = client.delete("/api/v1/workflows/crud_test_wf")
    assert del_resp.status_code == 200


def test_credentials_management_masked(client):
    cred_payload = {
        "id": "openai_test_key",
        "name": "OpenAI Test",
        "provider": "openai",
        "secret": "sk-proj-1234567890abcdef"
    }

    # Save
    save_resp = client.post("/api/v1/credentials", json=cred_payload)
    assert save_resp.status_code == 200

    # List & verify secret is masked
    list_resp = client.get("/api/v1/credentials")
    assert list_resp.status_code == 200
    creds = list_resp.json()
    found = next((c for c in creds if c["id"] == "openai_test_key"), None)
    assert found is not None
    assert "secret" not in found or found.get("secret") is None
    assert "sk-" in found["masked_hint"]
    assert "1234567890abcdef" not in found["masked_hint"]

    # Delete
    del_resp = client.delete("/api/v1/credentials/openai_test_key")
    assert del_resp.status_code == 200
