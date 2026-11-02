"""API and WebSocket tests for PHANTOMNET /ws/events and /api/replay endpoints."""

from __future__ import annotations

import msgpack
import pytest
from fastapi.testclient import TestClient
from phantomnet.bus import global_event_bus
from phantomnet.events import EventBatch, EventKind, PhantomEvent
from routelab.api.server import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_api_replay_synthetic_msgpack(client: TestClient) -> None:
    """Verify /api/replay/synthetic returns binary MessagePack payload with correct headers."""
    response = client.get("/api/replay/synthetic")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/msgpack"
    assert "x-run-hash" in response.headers
    assert int(response.headers["x-event-count"]) > 0

    batch = EventBatch.from_msgpack(response.content)
    assert len(batch.events) > 0
    assert any(e.kind == EventKind.HANDSHAKE_MSG for e in batch.events)
    assert any(e.kind == EventKind.BENCH_MARK for e in batch.events)


def test_api_replay_json(client: TestClient) -> None:
    """Verify /api/replay/synthetic supports application/json when requested."""
    response = client.get("/api/replay/synthetic", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "synthetic"
    assert "run_hash" in data
    assert isinstance(data["events"], list)
    assert len(data["events"]) > 0


def test_api_replay_filtering(client: TestClient) -> None:
    """Verify temporal and kind filtering on /api/replay."""
    response = client.get(
        "/api/replay/synthetic?kinds=PKT_TX,PKT_RX&start_t=1.0&end_t=3.0",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    data = response.json()
    for ev in data["events"]:
        assert ev["kind"] in ("PKT_TX", "PKT_RX")
        assert 1.0 <= ev["t"] <= 3.0


def test_api_runs_list(client: TestClient) -> None:
    """Verify /api/runs returns the available runs list."""
    response = client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data
    run_ids = [r["run_id"] for r in data["runs"]]
    assert "synthetic" in run_ids


def test_websocket_live_events(client: TestClient) -> None:
    """Verify /ws/events WebSocket connection and 60 Hz batched MessagePack streaming."""
    with client.websocket_connect("/ws/events") as ws:
        # Publish an event to the global bus
        ev = PhantomEvent(
            version=1,
            seq=1,
            t=0.01,
            kind=EventKind.PKT_TX,
            size=1420,
            dir="TX",
            meta={"test": True},
        )
        global_event_bus.publish_sync(ev)

        # Receive batched frame from WebSocket
        raw_msg = ws.receive_bytes()
        assert isinstance(raw_msg, bytes)

        batch_dict = msgpack.unpackb(raw_msg, raw=False)
        assert batch_dict["type"] == "event_batch"
        assert len(batch_dict["events"]) >= 1
        first_event = batch_dict["events"][0]
        assert first_event["kind"] == "PKT_TX"
        assert first_event["size"] == 1420
