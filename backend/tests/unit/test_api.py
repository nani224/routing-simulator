"""Unit and integration tests for FastAPI REST and WebSocket API endpoints."""

import pytest
from fastapi.testclient import TestClient
from routelab.api.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "RouteLab" in data["project"]


def test_list_topologies(client: TestClient) -> None:
    response = client.get("/api/v1/topologies")
    assert response.status_code == 200
    topos = response.json()
    assert len(topos) >= 4
    names = [t["name"] for t in topos]
    assert "Course-6-Node-Benchmark" in names
    assert "Course-8-Node-Benchmark" in names
    assert "Course-10-Node-Benchmark" in names


def test_get_topology(client: TestClient) -> None:
    response = client.get("/api/v1/topologies/Course-6-Node-Benchmark")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Course-6-Node-Benchmark"
    assert len(data["nodes"]) == 6
    assert len(data["links"]) == 8


def test_generate_topology(client: TestClient) -> None:
    # 1. Ring
    res = client.post(
        "/api/v1/topologies/generate",
        json={"kind": "ring", "node_count": 8, "name": "Dynamic-Ring"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["nodes"]) == 8
    assert len(data["links"]) == 8

    # 2. Grid
    res = client.post(
        "/api/v1/topologies/generate",
        json={"kind": "grid", "node_count": 9, "width": 3, "height": 3},
    )
    assert res.status_code == 200
    assert len(res.json()["nodes"]) == 9


def test_list_and_get_plugins(client: TestClient) -> None:
    res = client.get("/api/v1/plugins")
    assert res.status_code == 200
    plugins = res.json()
    names = [p["name"] for p in plugins]
    assert "distance_vector" in names
    assert "link_state" in names
    assert "bgp_lite" in names
    assert "flooding" in names

    # Details
    detail_res = client.get("/api/v1/plugins/distance_vector")
    assert detail_res.status_code == 200
    assert "split_horizon" in detail_res.json()["config_schema"]


def test_list_and_run_scenarios(client: TestClient) -> None:
    res = client.get("/api/v1/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) >= 5

    # Run scenario
    run_res = client.post(
        "/api/v1/scenarios/run",
        json={"file_name": "6_node_dv_vs_ls.json", "time_limit_s": 5.0},
    )
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["is_converged"] is True
    assert "metrics" in data


def test_simulation_lifecycle_and_events(client: TestClient) -> None:
    # 1. Start simulation
    start_res = client.post(
        "/api/v1/simulation/start",
        json={
            "topology_name": "Course-6-Node-Benchmark",
            "protocol_name": "distance_vector",
            "clock_mode": "virtual",
            "quiescence_window_s": 0.2,
        },
    )
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "started"

    # 2. Step
    step_res = client.post("/api/v1/simulation/step", json={"step_duration_s": 0.2})
    assert step_res.status_code == 200
    assert "current_time" in step_res.json()

    # 3. Dynamic event injection
    event_res = client.post(
        "/api/v1/simulation/event",
        json={"action": "link_down", "params": {"u": "A", "v": "B"}},
    )
    assert event_res.status_code == 200

    # 4. State query
    state_res = client.get("/api/v1/simulation/state")
    assert state_res.status_code == 200
    state = state_res.json()
    assert state["active"] is True
    assert len(state["nodes"]) == 6

    # 5. Export CSV & JSON
    csv_res = client.get("/api/v1/export/csv")
    assert csv_res.status_code == 200
    assert "timestamp" in csv_res.text

    json_res = client.get("/api/v1/export/json")
    assert json_res.status_code == 200
    assert "events" in json_res.json()

    # 6. Stop
    stop_res = client.post("/api/v1/simulation/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "stopped"


def test_simulation_compare_endpoint(client: TestClient) -> None:
    res = client.post(
        "/api/v1/simulation/compare",
        json={
            "topology_name": "Course-6-Node-Benchmark",
            "protocols": ["distance_vector", "link_state"],
            "events": [{"timestamp": 0.2, "action": "link_down", "params": {"u": "A", "v": "B"}}],
            "time_limit_s": 8.0,
            "quiescence_window_s": 0.3,
        },
    )
    assert res.status_code == 200
    report = res.json()
    assert "metrics" in report
    assert "distance_vector" in report["metrics"]
    assert "link_state" in report["metrics"]
    assert "winners" in report


def test_websocket_simulation(client: TestClient) -> None:
    with client.websocket_connect("/ws/simulation") as ws:
        # Initial state message
        init_msg = ws.receive_json()
        assert init_msg["type"] == "init"

        # Ping
        ws.send_json({"type": "ping"})
        pong_msg = ws.receive_json()
        assert pong_msg["type"] == "pong"
