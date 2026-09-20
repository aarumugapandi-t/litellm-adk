"""API routes for Master Agent orchestration, agent synthesis, and dynamic tool testing."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...agent.manager import master_agent_manager
from ...tools.dynamic_tool import SafeCodeSandbox

router = APIRouter(prefix="/manager", tags=["Manager Agent"])


class ConfigureManagerRequest(BaseModel):
    model: str = "gpt-4o"
    api_key: Optional[str] = None
    api_base: Optional[str] = None


class SynthesizeAgentRequest(BaseModel):
    prompt: str = Field(..., description="Natural language description of desired agent and capabilities")
    existing_workflow: Optional[Dict[str, Any]] = None


class TestDynamicToolRequest(BaseModel):
    code: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 10.0


@router.get("/status")
async def get_manager_status() -> Dict[str, Any]:
    """Returns Master Agent configuration state and model availability."""
    return master_agent_manager.get_status()


@router.post("/configure")
async def configure_manager(req: ConfigureManagerRequest) -> Dict[str, Any]:
    """Updates the Master Agent LLM model, API key, and optional base URL."""
    return master_agent_manager.configure(
        model=req.model,
        api_key=req.api_key,
        api_base=req.api_base,
    )


@router.post("/test-connection")
async def test_connection() -> Dict[str, Any]:
    """Tests LLM connectivity for the configured Master Agent."""
    return await master_agent_manager.test_connection()


@router.post("/synthesize")
async def synthesize_agent(req: SynthesizeAgentRequest) -> Dict[str, Any]:
    """Synthesizes AgentSpec, Dynamic Tools, and visual canvas wiring from natural language prompt."""
    try:
        return await master_agent_manager.synthesize_agent(
            prompt=req.prompt,
            existing_workflow=req.existing_workflow,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tools/test")
async def test_dynamic_tool(req: TestDynamicToolRequest) -> Dict[str, Any]:
    """Executes dynamic tool Python code inside a restricted sandbox and returns output."""
    res = await SafeCodeSandbox.execute(
        code=req.code,
        arguments=req.arguments,
        timeout_seconds=req.timeout_seconds,
    )
    return res.model_dump()


@router.get("/templates")
async def get_manager_templates() -> List[Dict[str, Any]]:
    """Returns curated starter prompts for autonomous agent generation."""
    return [
        {
            "id": "customer_support",
            "title": "Customer Support & DB Resolver",
            "prompt": "Create a Customer Support Agent that queries PostgreSQL database for order status, searches refund policy docs, and sends an email alert with human approval when escalation is required.",
            "category": "Customer Ops",
            "tags": ["Postgres", "Docs Search", "Email", "Approval"],
        },
        {
            "id": "sales_analytics",
            "title": "Sales & Revenue Analytics Agent",
            "prompt": "Create a Sales Analytics Agent that extracts raw sales figures, computes KPI metrics and variance percentages, and generates an executive summary report.",
            "category": "Analytics",
            "tags": ["KPI Metrics", "Calculations", "Reporting"],
        },
        {
            "id": "market_research",
            "title": "Market & Competitor Researcher",
            "prompt": "Create an AI Research Agent that searches live web sources for competitor launches, extracts sentiment, and summarizes key strategic findings.",
            "category": "Research",
            "tags": ["Web Search", "Synthesis", "Market Intelligence"],
        },
        {
            "id": "devops_sentry",
            "title": "DevOps Incident Monitor",
            "prompt": "Create a DevOps Sentry Agent that queries server health endpoints via HTTP, checks error thresholds, and generates an incident ticket when anomalies occur.",
            "category": "DevOps",
            "tags": ["HTTP API", "Health Check", "Incident Alert"],
        },
    ]
