"""A.10.1 /api/campus/* Blueprint 集成测试。"""
import sqlite3

import pytest
import simpy


@pytest.fixture
def client(tmp_path, monkeypatch):
    """每个测试使用独立 SQLite 与全新单例 session。"""
    db_path = tmp_path / "test.db"
    import api.routes as routes

    monkeypatch.setattr(routes, "DB_PATH", str(db_path))
    monkeypatch.setattr(routes, "_session", {
        "mode": None,
        "engine": None,
        "coordinator": None,
        "config_id": None,
        "is_running": False,
        "snapshot_buffer": [],
    })

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def make_campus_payload(simulation_seconds=8):
    canteens = []
    for cid, pos in [
        ("minghu_xueyi", {"x": 0, "y": 0}),
        ("xuehuo", {"x": 80, "y": 0}),
        ("xuesi", {"x": 0, "y": 80}),
    ]:
        canteens.append({
            "id": cid,
            "display_name": cid,
            "campus_position": pos,
            "avg_serve_time_seconds": 2,
            "avg_eat_time_minutes": 1,
            "arrival_weight": 1.0,
            "typical_wait_seconds": 10,
            "floors": [{
                "floor_id": 1,
                "windows": {"physical_count": 3, "active_count": 3},
                "seats": {"count": 60},
            }],
        })

    return {
        "campus": {
            "total_students": 900,
            "lunch_alpha": 1.0,
            "coverage": 1.0,
            "peak_window_minutes": 10,
            "peak_beta": 1.5,
            "simulation_seconds": simulation_seconds,
            "entrance_position": {"x": 0, "y": 0},
            "walking_speed_mps": 1.4,
            "walking_time_seconds": {},
            "entrance_walk_seconds": {
                "minghu_xueyi": 1,
                "xuehuo": 1,
                "xuesi": 1,
            },
        },
        "canteens": canteens,
        "router": {
            "information_mode": "local_estimate",
            "patience_mean_seconds": 180,
            "patience_std_seconds": 30,
            "patience_min_seconds": 30,
            "switch_improvement_ratio": 1.3,
            "max_switches_per_student": 2,
            "rng_seed": 42,
        },
    }


SINGLE_CONFIG = {
    "window_count": 3,
    "seat_count": 30,
    "avg_serve_time": 15,
    "avg_eat_time": 5,
    "arrival_rate": 20,
    "total_time": 5,
}


def test_post_campus_config_returns_canteen_order(client):
    res = client.post("/api/campus/config", json=make_campus_payload())

    assert res.status_code == 200
    body = res.get_json()
    assert body["mode"] == "campus"
    assert body["canteen_order"] == ["minghu_xueyi", "xuehuo", "xuesi"]


def test_campus_default_preset_endpoint(client):
    resp = client.get("/api/campus/presets/default")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "campus"
    assert data["pending_canteens"] == ["xuehuo"]
    assert [c["id"] for c in data["config"]["canteens"]] == [
        "minghu_xueyi",
        "xuesi",
    ]
    visible = [c["id"] for c in data["visible_canteens"]]
    assert visible == ["minghu_xueyi", "xuehuo", "xuesi"]


def test_campus_step_advances_display_tick(client):
    client.post("/api/campus/config", json=make_campus_payload())
    client.post("/api/campus/start")

    res = client.get("/api/campus/step?display_tick_seconds=10")

    assert res.status_code == 200
    body = res.get_json()
    assert body["mode"] == "campus"
    assert body["current_time"] >= 10
    assert "campus_totals" in body


def test_campus_finish_drains_simulation(client):
    client.post("/api/campus/config", json=make_campus_payload(simulation_seconds=5))
    client.post("/api/campus/start")

    res = client.post("/api/campus/finish")

    assert res.status_code == 200
    body = res.get_json()
    assert body["mode"] == "campus"
    assert body["campus_totals"]["total_arrived"] == body["campus_totals"]["total_served"]
    assert body["campus_totals"]["total_arrived"] > 0
    assert body["fast_forward_steps"] >= 0


def test_campus_step_flushes_snapshot_buffer_in_batches(client):
    import api.routes as routes

    client.post("/api/campus/config", json=make_campus_payload(simulation_seconds=300))
    client.post("/api/campus/start")

    for _ in range(60):
        res = client.get("/api/campus/step?display_tick_seconds=1")
        assert res.status_code == 200

    assert len(routes._session["snapshot_buffer"]) < 50
    with sqlite3.connect(routes.DB_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM campus_snapshot").fetchone()[0]
    assert count >= 50


def test_campus_finish_records_timeline_snapshots(client):
    import api.routes as routes

    client.post("/api/campus/config", json=make_campus_payload(simulation_seconds=35))
    client.post("/api/campus/start")
    res = client.post("/api/campus/finish")
    assert res.status_code == 200

    with sqlite3.connect(routes.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT s.current_time, s.event_type FROM campus_snapshot s ORDER BY s.current_time"
        ).fetchall()

    assert len(rows) > 1
    assert rows[-1][1] == "finish"
    assert [row[0] for row in rows] == sorted(row[0] for row in rows)


def test_campus_history_endpoints_read_campus_snapshots(client):
    cfg = client.post(
        "/api/campus/config", json=make_campus_payload(simulation_seconds=35)
    ).get_json()
    client.post("/api/campus/start")
    client.post("/api/campus/finish")

    configs = client.get("/api/campus/history/configs").get_json()
    record = next(item for item in configs if item["id"] == cfg["config_id"])
    assert record["mode"] == "campus"
    assert record["snapshot_count"] > 1
    assert record["total_arrived"] == record["total_served"]

    history = client.get(
        f"/api/campus/history?config_id={cfg['config_id']}"
    ).get_json()
    assert len(history) == record["snapshot_count"]
    assert history[0]["config_id"] == cfg["config_id"]
    assert "campus_totals" in history[0]
    assert "canteens" in history[0]
    assert "in_transit" in history[0]


def test_campus_finish_records_strict_display_tick_snapshots(client):
    import api.routes as routes

    payload = make_campus_payload(simulation_seconds=120)
    payload["campus"]["total_students"] = 1
    payload["campus"]["peak_window_minutes"] = 120
    client.post("/api/campus/config", json=payload)
    client.post("/api/campus/start")
    res = client.post("/api/campus/finish?display_tick_seconds=10")
    assert res.status_code == 200

    with sqlite3.connect(routes.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT s.current_time, s.event_type FROM campus_snapshot s ORDER BY s.current_time"
        ).fetchall()

    step_times = [round(row[0], 6) for row in rows if row[1] == "step"]
    assert step_times[:4] == [10, 20, 30, 40]
    assert 120 in step_times
    assert len(step_times) >= 12


def test_advance_to_display_time_does_not_run_past_max_steps():
    from api.campus_routes import _advance_to_display_time

    env = simpy.Environment()
    processed_times = []
    for delay in range(1, 11):
        event = env.timeout(delay)
        event.callbacks.append(lambda e: processed_times.append(e.env.now))

    coordinator = type("CoordinatorProbe", (), {"env": env})()
    steps = _advance_to_display_time(
        coordinator, target_time=10, steps=0, max_steps=5
    )

    assert steps == 5
    assert processed_times == [1, 2, 3, 4, 5]
    assert env.now == 5


def test_campus_statistics_returns_aggregate_metrics_not_raw_snapshot(client):
    client.post("/api/campus/config", json=make_campus_payload(simulation_seconds=5))
    client.post("/api/campus/start")
    client.post("/api/campus/finish")

    res = client.get("/api/campus/statistics")

    assert res.status_code == 200
    body = res.get_json()
    assert body["mode"] == "campus"
    assert "campus_totals" not in body
    assert "in_transit" not in body
    for field in [
        "total_arrived",
        "total_served",
        "avg_waiting_time",
        "avg_service_time",
        "avg_eating_time",
        "avg_walk_time",
        "switch_rate",
        "window_served",
        "seat_utilization",
        "peak_queue_length",
        "queue_timeline",
        "seat_util_timeline",
        "canteen_statistics",
    ]:
        assert field in body


def test_campus_status_returns_mode_field(client):
    empty = client.get("/api/campus/status").get_json()
    assert empty["mode"] is None
    assert empty["initialized"] is False

    client.post("/api/campus/config", json=make_campus_payload())
    status = client.get("/api/campus/status").get_json()
    assert status["mode"] == "campus"
    assert status["initialized"] is True


def test_single_campus_session_isolation(client):
    single = client.post("/api/config", json=SINGLE_CONFIG)
    assert single.status_code == 200

    blocked = client.post("/api/campus/config", json=make_campus_payload())
    assert blocked.status_code == 400
    assert "reset" in blocked.get_json()["error"]

    client.post("/api/simulation/reset")
    campus = client.post("/api/campus/config", json=make_campus_payload())
    assert campus.status_code == 200
