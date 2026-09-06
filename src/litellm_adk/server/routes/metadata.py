"""Metadata endpoints for node discovery, tool registration, and credentials."""

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ...workflow.nodes.registry import node_registry
from ...tools.registry import tool_registry
from ...persistence.sqlite_workflow import credential_repository

router = APIRouter(tags=["Metadata"])


class CredentialPayload(BaseModel):
    id: str
    name: str
    provider: str
    secret: str


@router.get("/nodes")
async def list_available_nodes() -> List[Dict[str, Any]]:
    """Discovers all registered workflow node types and their configuration schemas."""
    definitions = node_registry.list_definitions()
    return [d.model_dump() for d in definitions]


@router.get("/tools")
async def list_available_tools() -> List[Dict[str, Any]]:
    """Lists all tools currently registered in the ADK ToolRegistry."""
    tools = []
    for name, tool_obj in tool_registry._tools.items():
        tools.append({
            "name": name,
            "description": getattr(tool_obj, "description", ""),
            "parameters": getattr(tool_obj, "parameters_schema", {}),
            "requires_approval": getattr(tool_obj, "requires_approval", False),
        })
    return tools


@router.get("/credentials")
async def list_credentials() -> List[Dict[str, Any]]:
    """Lists configured provider credentials with secrets safely masked."""
    return await credential_repository.list_all()


@router.post("/credentials")
async def save_credential(payload: CredentialPayload) -> Dict[str, str]:
    """Saves or updates a provider API credential."""
    await credential_repository.save(
        cred_id=payload.id,
        name=payload.name,
        provider=payload.provider,
        secret=payload.secret,
    )
    return {"status": "saved", "id": payload.id}


@router.delete("/credentials/{cred_id}")
async def delete_credential(cred_id: str) -> Dict[str, bool]:
    """Removes a stored credential."""
    deleted = await credential_repository.delete(cred_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Credential '{cred_id}' not found.")
    return {"deleted": True}


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "litellm-adk-workflow-server",
        "version": "1.0.0"
    }
