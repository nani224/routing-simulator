"""FastAPI routes and WebSocket handlers for PHANTOMNET event spine."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse

from phantomnet.bus import PhantomEventBus, global_event_bus
from phantomnet.events import EventBatch, EventKind, PhantomEvent
from phantomnet.synthetic import generate_synthetic_episode

router = APIRouter(tags=["phantomnet"])

# Store preloaded or recorded runs in-memory
run_store: dict[str, PhantomEventBus] = {}


def get_or_create_run_bus(run_id: str) -> PhantomEventBus:
    """Retrieve an existing run EventBus or initialize a synthetic episode."""
    if run_id in run_store:
        return run_store[run_id]

    if run_id in ("synthetic", "default", "synthetic-episode", "scripted-episode"):
        bus = PhantomEventBus(run_id=run_id)
        events = generate_synthetic_episode(seed=42)
        for ev in events:
            bus.publish_sync(ev)
        run_store[run_id] = bus
        return bus

    raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")


@router.websocket("/ws/events")
async def websocket_events(
    websocket: WebSocket,
    kinds: str | None = Query(default=None, description="Comma-separated event kinds filter"),
    since_seq: int = Query(default=0, ge=0, description="Resume stream from sequence number"),
) -> None:
    """Live 60 Hz batched MessagePack event streaming WebSocket."""
    await websocket.accept()

    kind_filter: set[EventKind] | None = None
    if kinds:
        kind_filter = {EventKind(k.strip()) for k in kinds.split(",") if k.strip()}

    queue = global_event_bus.subscribe(maxsize=10_000)
    batch_seq = 0
    target_frame_time = 1.0 / 60.0  # 60 Hz interval (~16.67ms)

    try:
        # If client requested replay from sequence, stream backlog first
        if since_seq > 0:
            backlog = global_event_bus.get_since_seq(since_seq, limit=2000)
            if kind_filter:
                backlog = [e for e in backlog if e.kind in kind_filter]
            if backlog:
                batch = EventBatch(
                    batch_seq=batch_seq,
                    timestamp=time.time(),
                    run_id=global_event_bus.run_id,
                    events=backlog,
                )
                batch_seq += 1
                await websocket.send_bytes(batch.to_msgpack())

        while True:
            start_tick = time.monotonic()
            batch_events: list[PhantomEvent] = []

            # Drain all currently available events from queue
            while True:
                try:
                    event = queue.get_nowait()
                    if kind_filter is None or event.kind in kind_filter:
                        batch_events.append(event)
                except asyncio.QueueEmpty:
                    break

            if batch_events:
                batch = EventBatch(
                    batch_seq=batch_seq,
                    timestamp=time.time(),
                    run_id=global_event_bus.run_id,
                    events=batch_events,
                )
                batch_seq += 1
                await websocket.send_bytes(batch.to_msgpack())

            elapsed = time.monotonic() - start_tick
            sleep_time = max(0.001, target_frame_time - elapsed)
            await asyncio.sleep(sleep_time)

    except WebSocketDisconnect:
        pass
    finally:
        global_event_bus.unsubscribe(queue)


@router.get("/api/replay/{run_id}")
async def get_replay_run(
    run_id: str,
    start_t: float = Query(default=0.0, ge=0.0),
    end_t: float | None = Query(default=None, ge=0.0),
    kinds: str | None = Query(default=None),
    since_seq: int = Query(default=0, ge=0),
    accept: str | None = Header(default="application/msgpack"),
) -> Response:
    """Retrieve recorded or synthetic run events for temporal scrubbing and replay."""
    bus = get_or_create_run_bus(run_id)

    kind_filter: set[EventKind] | None = None
    if kinds:
        kind_filter = {EventKind(k.strip()) for k in kinds.split(",") if k.strip()}

    if since_seq > 0:
        events = bus.get_since_seq(since_seq)
        if kind_filter:
            events = [e for e in events if e.kind in kind_filter]
    else:
        events = bus.get_range(start_t=start_t, end_t=end_t, kinds=kind_filter)

    run_hash = bus.get_run_hash()
    headers = {
        "X-Run-Hash": run_hash,
        "X-Run-Id": run_id,
        "X-Event-Count": str(len(events)),
    }

    if accept and "application/json" in accept:
        content_dict: dict[str, Any] = {
            "run_id": run_id,
            "run_hash": run_hash,
            "count": len(events),
            "events": [e.to_dict() for e in events],
        }
        return JSONResponse(content=content_dict, headers=headers)

    # Default binary MessagePack payload
    batch = EventBatch(
        batch_seq=0,
        timestamp=time.time(),
        run_id=run_id,
        events=events,
    )
    return Response(
        content=batch.to_msgpack(),
        media_type="application/msgpack",
        headers=headers,
    )


@router.get("/api/runs")
def list_available_runs() -> dict[str, Any]:
    """List available recorded and synthetic runs."""
    # Ensure synthetic run is available
    get_or_create_run_bus("synthetic")
    return {
        "runs": [
            {
                "run_id": rid,
                "event_count": bus.count(),
                "run_hash": bus.get_run_hash(),
            }
            for rid, bus in run_store.items()
        ]
    }
