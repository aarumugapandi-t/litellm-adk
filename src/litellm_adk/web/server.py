import json
import asyncio
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import os

def create_ui_app(agent):
    app = FastAPI(title="LiteLLM ADK Web UI")
    
    # Get current directory for static files
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def get_ui():
        with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
            return f.read()

    @app.post("/chat")
    async def chat(request: Request):
        data = await request.json()
        prompt = data.get("message")
        session_id = data.get("session_id")
        response = await agent.ainvoke(prompt, session_id=session_id)
        if isinstance(response, dict):
            return {"response": json.dumps(response, indent=2)}
        return {"response": str(response)}

    @app.post("/chat/stream")
    async def stream_chat(request: Request):
        data = await request.json()
        prompt = data.get("message")
        session_id = data.get("session_id")

        async def event_generator():
            async for event in agent.astream(prompt, session_id=session_id, stream_events=True):
                # Handle structured events
                if isinstance(event, dict):
                    etype = event.get("type")
                    if etype == "delta" or etype == "content":
                        content = event.get("delta") or event.get("content")
                        if content:
                            yield f"data: {json.dumps({'type': 'delta', 'content': content})}\n\n"
                    elif etype == "tool_start":
                        yield f"data: {json.dumps({'type': 'tool_start', 'name': event.get('name')})}\n\n"
                    elif etype == "tool_end":
                        yield f"data: {json.dumps({'type': 'tool_end', 'name': event.get('name')})}\n\n"
                elif isinstance(event, str):
                    yield f"data: {json.dumps({'type': 'delta', 'content': event})}\n\n"
            
            yield "data: {\"type\": \"done\"}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/sessions")
    async def get_sessions():
        sessions = []
        if hasattr(agent, 'memory') and agent.memory:
             sessions = agent.memory.list_sessions()
        return {"sessions": sessions}

    @app.get("/sessions/{session_id}/history")
    async def get_history(session_id: str):
        history = []
        if hasattr(agent, 'memory') and agent.memory:
            history = agent.memory.get_messages(session_id)
        
        # Format history for UI
        formatted = []
        for msg in history:
            if msg["role"] in ["user", "assistant"]:
                item = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                if msg["role"] == "assistant" and "tool_calls" in msg:
                    item["tool_calls"] = [tc["function"]["name"] for tc in msg["tool_calls"]]
                formatted.append(item)
        return {"history": formatted}

    return app
