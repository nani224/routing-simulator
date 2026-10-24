"""WebSocket router for live event streaming and interactive telemetry."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from routelab.api.state import session_manager

logger = logging.getLogger("routelab.api.ws")
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/simulation")
async def websocket_simulation_endpoint(websocket: WebSocket) -> None:
    """Live WebSocket stream broadcasting delta updates and accepting interactive commands."""
    await session_manager.register_client(websocket)
    try:
        while True:
            # Receive client interactions (e.g. ping, step requests, event injections)
            data = await websocket.receive_json()
            cmd_type = data.get("type")

            if cmd_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif cmd_type == "step":
                duration = float(data.get("duration_s", 0.1))
                res = await session_manager.step(duration)
                await websocket.send_json({"type": "step_result", "result": res})
            elif cmd_type == "inject_event":
                action = str(data.get("action"))
                params = dict(data.get("params", {}))
                res = await session_manager.inject_event(action, params)
                await websocket.send_json({"type": "event_result", "result": res})
            elif cmd_type == "get_state":
                state = session_manager.get_state()
                await websocket.send_json({"type": "state", "state": state})

    except WebSocketDisconnect:
        session_manager.unregister_client(websocket)
    except Exception as exc:
        logger.debug("WebSocket client disconnected with exception: %s", exc)
        session_manager.unregister_client(websocket)
