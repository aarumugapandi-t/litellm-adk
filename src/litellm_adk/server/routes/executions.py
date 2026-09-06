"""Execution inspection, status polling, and human approval resumption endpoints."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from ...workflow.engine import WorkflowEngine
from ...workflow.state import ExecutionStatus
from ...persistence.sqlite_workflow import execution_repository, workflow_repository
from .stream import stream_manager

router = APIRouter(tags=["Executions"])


class ApproveRequest(BaseModel):
    approved: bool = True
    user_input: Optional[str] = None
    selected_option: Optional[str] = None
    feedback: Optional[str] = None


async def _resume_workflow_background(
    exec_id: str,
    human_decision: Dict[str, Any]
):
    state = await execution_repository.get(exec_id)
    if not state:
        return
    wf = await workflow_repository.get(state.workflow_id)
    if not wf:
        return

    engine = WorkflowEngine()

    async def _on_event(e_type: str, data: Dict[str, Any]):
        await stream_manager.broadcast(exec_id, data)

    engine.subscribe(_on_event)

    new_state = await engine.execute(
        workflow=wf,
        existing_state=state,
        human_decision=human_decision,
    )
    await execution_repository.save(new_state)


@router.get("/executions")
async def list_executions(
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Lists past and running workflow executions."""
    return await execution_repository.list_all(workflow_id=workflow_id, status=status, limit=limit)


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str) -> Dict[str, Any]:
    """Retrieves full execution state, node execution metrics, and logs."""
    state = await execution_repository.get(execution_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found.")
    return state.model_dump()


@router.post("/executions/{execution_id}/approve")
async def approve_execution(
    execution_id: str,
    req: ApproveRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Submits a human approval or rejection decision to resume a paused execution."""
    state = await execution_repository.get(execution_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found.")

    if state.status != ExecutionStatus.WAITING_FOR_HUMAN:
        raise HTTPException(
            status_code=400,
            detail=f"Execution '{execution_id}' is in '{state.status.value}' state and is not awaiting approval."
        )

    decision_data = {
        "approved": req.approved,
        "user_input": req.user_input,
        "selected_option": req.selected_option,
        "feedback": req.feedback,
    }

    # Resume execution in background
    background_tasks.add_task(_resume_workflow_background, execution_id, decision_data)

    return {
        "status": "resuming",
        "execution_id": execution_id,
        "decision": decision_data
    }
