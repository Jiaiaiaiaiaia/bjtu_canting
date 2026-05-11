"""A.10.1 /api/campus/* Blueprint 集成测试。"""
import pytest


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
