"""WebSocket and SSE streaming hub for real-time workflow execution updates."""

import asyncio
import json
from collections import defaultdict
from typing import Any, Dict, List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["Streaming"])


class ConnectionManager:
    """Manages active WebSocket connections per execution ID."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.event_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    async def connect(self, execution_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[execution_id].add(websocket)
        # Replay any existing events for this execution
        for event in self.event_history.get(execution_id, []):
            try:
                await websocket.send_text(json.dumps(event))
            except Exception:
                pass

    def disconnect(self, execution_id: str, websocket: WebSocket):
        if execution_id in self.active_connections:
            self.active_connections[execution_id].discard(websocket)
            if not self.active_connections[execution_id]:
                del self.active_connections[execution_id]

    async def broadcast(self, execution_id: str, event: Dict[str, Any]):
        self.event_history[execution_id].append(event)
        if execution_id in self.active_connections:
            msg = json.dumps(event)
            dead_conns = []
            for connection in list(self.active_connections[execution_id]):
                try:
                    await connection.send_text(msg)
                except Exception:
                    dead_conns.append(connection)
            for dead in dead_conns:
                self.disconnect(execution_id, dead)


stream_manager = ConnectionManager()


@router.websocket("/executions/{execution_id}/stream")
async def websocket_execution_stream(websocket: WebSocket, execution_id: str):
    """WebSocket stream emitting live node-by-node execution events."""
    await stream_manager.connect(execution_id, websocket)
    try:
        while True:
            # Keep alive; receive any ping/acknowledgement from client
            await websocket.receive_text()
    except WebSocketDisconnect:
        stream_manager.disconnect(execution_id, websocket)


@router.get("/executions/{execution_id}/events")
async def sse_execution_events(execution_id: str):
    """Server-Sent Events (SSE) fallback stream for execution events."""
    async def event_generator():
        queue = asyncio.Queue()

        def _listener(e_type: str, data: Dict[str, Any]):
            queue.put_nowait(data)

        # Send existing history first
        for ev in stream_manager.event_history.get(execution_id, []):
            yield f"data: {json.dumps(ev)}\n\n"

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("workflow.completed", "workflow.failed"):
                    break
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
