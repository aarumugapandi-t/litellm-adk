"""Workflow definition management, lifecycle, and execution trigger endpoints."""

import asyncio
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from ...workflow.schema import WorkflowDefinition, WorkflowStatus
from ...workflow.engine import WorkflowEngine
from ...persistence.sqlite_workflow import workflow_repository, execution_repository
from .stream import stream_manager

router = APIRouter(tags=["Workflows"])


class ExecuteWorkflowRequest(BaseModel):
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    run_async: bool = True


class ExecuteWorkflowResponse(BaseModel):
    execution_id: str
    workflow_id: str
    status: str
    outputs: Optional[Dict[str, Any]] = None


async def _run_workflow_background(
    workflow: WorkflowDefinition,
    trigger_data: Dict[str, Any],
    exec_id: str
):
    """Background task running the workflow engine and persisting final state."""
    engine = WorkflowEngine()

    async def _on_event(e_type: str, data: Dict[str, Any]):
        await stream_manager.broadcast(exec_id, data)

    engine.subscribe(_on_event)

    state = await engine.execute(workflow, trigger_data=trigger_data)
    state.execution_id = exec_id
    await execution_repository.save(state)


@router.get("/workflows")
async def list_workflows() -> List[Dict[str, Any]]:
    """Returns all saved workflow definitions."""
    wfs = await workflow_repository.list_all()
    return [w.model_dump() for w in wfs]


@router.post("/workflows")
async def create_workflow(workflow: WorkflowDefinition) -> Dict[str, Any]:
    """Creates and persists a new workflow definition."""
    if not workflow.id:
        workflow.id = f"wf_{uuid.uuid4().hex[:10]}"
    await workflow_repository.save(workflow)
    return {"status": "created", "workflow": workflow.model_dump()}


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str) -> Dict[str, Any]:
    """Retrieves a single workflow definition by ID."""
    wf = await workflow_repository.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return wf.model_dump()


@router.put("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, workflow: WorkflowDefinition) -> Dict[str, Any]:
    """Updates an existing workflow definition and bumps version history."""
    existing = await workflow_repository.get(workflow_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    workflow.id = workflow_id
    await workflow_repository.save(workflow)
    return {"status": "updated", "workflow": workflow.model_dump()}


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str) -> Dict[str, bool]:
    """Deletes a workflow definition."""
    deleted = await workflow_repository.delete(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return {"deleted": True}


@router.post("/workflows/{workflow_id}/activate")
async def activate_workflow(workflow_id: str) -> Dict[str, Any]:
    """Activates a workflow for production triggers."""
    wf = await workflow_repository.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    wf.active = True
    wf.status = WorkflowStatus.ACTIVE
    await workflow_repository.save(wf)
    return {"status": "activated", "active": True}


@router.post("/workflows/{workflow_id}/deactivate")
async def deactivate_workflow(workflow_id: str) -> Dict[str, Any]:
    """Deactivates a workflow."""
    wf = await workflow_repository.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    wf.active = False
    wf.status = WorkflowStatus.INACTIVE
    await workflow_repository.save(wf)
    return {"status": "deactivated", "active": False}


@router.post("/workflows/{workflow_id}/duplicate")
async def duplicate_workflow(workflow_id: str) -> Dict[str, Any]:
    """Duplicates an existing workflow."""
    wf = await workflow_repository.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    new_wf = wf.model_copy(deep=True)
    new_wf.id = f"wf_{uuid.uuid4().hex[:10]}"
    new_wf.name = f"{wf.name} (Copy)"
    new_wf.active = False
    new_wf.status = WorkflowStatus.DRAFT
    await workflow_repository.save(new_wf)
    return {"status": "duplicated", "workflow": new_wf.model_dump()}


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    req: ExecuteWorkflowRequest,
    background_tasks: BackgroundTasks
) -> ExecuteWorkflowResponse:
    """Executes a workflow asynchronously or synchronously."""
    wf = await workflow_repository.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")

    exec_id = f"exec_{uuid.uuid4().hex[:12]}"

    if req.run_async:
        background_tasks.add_task(_run_workflow_background, wf, req.trigger_data, exec_id)
        return ExecuteWorkflowResponse(
            execution_id=exec_id,
            workflow_id=wf.id,
            status="running"
        )
    else:
        # Run synchronously
        engine = WorkflowEngine()

        async def _on_event(e_type: str, data: Dict[str, Any]):
            await stream_manager.broadcast(exec_id, data)

        engine.subscribe(_on_event)
        state = await engine.execute(wf, trigger_data=req.trigger_data)
        state.execution_id = exec_id
        await execution_repository.save(state)
        return ExecuteWorkflowResponse(
            execution_id=exec_id,
            workflow_id=wf.id,
            status=state.status.value,
            outputs=state.node_outputs,
        )


@router.get("/workflows/{workflow_id}/export")
async def export_workflow(workflow_id: str) -> Dict[str, Any]:
    """Exports workflow definition as JSON."""
    wf = await workflow_repository.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return wf.model_dump()


@router.post("/workflows/import")
async def import_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Imports a workflow definition from JSON."""
    try:
        wf = WorkflowDefinition.model_validate(payload)
        # Ensure fresh ID if ID already exists or empty
        if not wf.id or await workflow_repository.get(wf.id):
            wf.id = f"wf_{uuid.uuid4().hex[:10]}"
        await workflow_repository.save(wf)
        return {"status": "imported", "workflow": wf.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid workflow specification: {e}")
