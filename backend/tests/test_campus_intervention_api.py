import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    """每个测试使用独立 SQLite 与全新单例 session（镜像 test_campus_api.py）。"""
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

def _start_single(client):
    pre = client.get("/api/campus/presets/single-canteen").get_json()
    client.post("/api/campus/config", json=pre["config"])
    client.post("/api/campus/start")

def test_intervention_visible_in_history_immediately(client):
    _start_single(client)
    client.get("/api/campus/step?display_tick_seconds=5")
    cfg = client.get("/api/campus/status").get_json()
    cid = cfg["canteen_order"][0]
    res = client.post(f"/api/campus/canteens/{cid}/windows/0/toggle",
                       json={"open": False})
    assert res.status_code == 200
    body = res.get_json()
    assert body["interventions"][-1]["window_id"] == 0
    hist = client.get("/api/campus/history").get_json()
    assert any(h.get("interventions") and
               any(i["window_id"] == 0 for i in h["interventions"])
               for h in hist)


def test_toggle_response_exposes_closed_window_state_for_3d_ui(client):
    _start_single(client)
    cfg = client.get("/api/campus/status").get_json()
    cid = cfg["canteen_order"][0]

    res = client.post(f"/api/campus/canteens/{cid}/windows/0/toggle",
                      json={"open": False})

    assert res.status_code == 200
    body = res.get_json()
    flat = next(w for w in body["canteens"][cid]["windows"] if w["id"] == 0)
    nested = next(
        w for floor in body["canteens"][cid]["floors"]
        for w in floor["windows"]
        if w["id"] == 0
    )
    assert flat["is_open"] is False
    assert flat["closing"] is False
    assert nested["is_open"] is False
    assert nested["closing"] is False


def test_toggle_event_contains_stable_id_and_before_after_metrics(client):
    _start_single(client)
    client.get("/api/campus/step?display_tick_seconds=60")
    cfg = client.get("/api/campus/status").get_json()
    cid = cfg["canteen_order"][0]

    res = client.post(f"/api/campus/canteens/{cid}/windows/0/toggle",
                      json={"open": False})

    assert res.status_code == 200
    event = res.get_json()["interventions"][-1]
    assert event["event_id"] == 1
    assert event["event_type"] == "window_toggle"
    assert event["changed"] is True
    assert event["metrics_before"]["open_window_count"] - 1 == (
        event["metrics_after"]["open_window_count"]
    )
    assert event["metrics_before"]["target_window_is_open"] is True
    assert event["metrics_after"]["target_window_is_open"] is False
    assert "campus_total_in_queue" in event["metrics_before"]
    assert "floor_total_in_queue" in event["metrics_after"]


def test_single_canteen_preset_starts_without_standby_add_switches(client):
    _start_single(client)
    snapshot = client.get("/api/campus/step?display_tick_seconds=1").get_json()
    cfg = client.get("/api/campus/status").get_json()
    cid = cfg["canteen_order"][0]
    floors = snapshot["canteens"][cid]["floors"]

    assert all(
        len(floor["windows"]) == sum(1 for w in floor["windows"] if w["is_open"])
        for floor in floors
    )


def test_add_window_intervention_creates_visible_window_event(client):
    _start_single(client)
    snapshot = client.get("/api/campus/step?display_tick_seconds=1").get_json()
    cfg = client.get("/api/campus/status").get_json()
    cid = cfg["canteen_order"][0]
    floor_id = 3
    before_floor = next(
        f for f in snapshot["canteens"][cid]["floors"]
        if f["floor_id"] == floor_id
    )
    before_count = len(before_floor["windows"])
    before_open = sum(1 for w in before_floor["windows"] if w["is_open"])

    res = client.post(
        f"/api/campus/canteens/{cid}/floors/{floor_id}/windows/add"
    )

    assert res.status_code == 200
    body = res.get_json()
    after_floor = next(
        f for f in body["canteens"][cid]["floors"]
        if f["floor_id"] == floor_id
    )
    new_windows = [
        w for w in after_floor["windows"]
        if w["id"] not in {w["id"] for w in before_floor["windows"]}
    ]
    assert len(after_floor["windows"]) == before_count + 1
    assert sum(1 for w in after_floor["windows"] if w["is_open"]) == before_open + 1
    assert len(new_windows) == 1
    assert new_windows[0]["is_open"] is True

    event = body["interventions"][-1]
    assert event["event_type"] == "window_add"
    assert event["action"] == "add"
    assert event["floor_id"] == floor_id
    assert event["window_id"] == new_windows[0]["id"]
    assert event["status"] == "applied"
    assert event["changed"] is True
    assert event["metrics_after"]["open_window_count"] == (
        event["metrics_before"]["open_window_count"] + 1
    )

    stats = client.get("/api/campus/statistics").get_json()
    effect = stats["intervention_analysis"]["events"][-1]
    assert effect["event_type"] == "window_add"
    assert effect["action"] == "add"
    assert "添加窗口" in effect["summary"]


def test_campus_statistics_dedupes_and_summarizes_intervention_effect(client):
    _start_single(client)
    client.get("/api/campus/step?display_tick_seconds=60")
    cfg = client.get("/api/campus/status").get_json()
    cid = cfg["canteen_order"][0]
    client.post(f"/api/campus/canteens/{cid}/windows/0/toggle",
                json={"open": False})
    client.get("/api/campus/step?display_tick_seconds=60")

    stats = client.get("/api/campus/statistics").get_json()
    analysis = stats["intervention_analysis"]

    assert analysis["total_events"] == 1
    assert analysis["applied_count"] == 1
    assert analysis["rejected_count"] == 0
    assert analysis["summary"].startswith("已记录 1 次窗口干预")
    event = analysis["events"][0]
    assert event["event_id"] == 1
    assert event["action"] == "close"
    assert event["open_window_delta"] == -1
    assert event["queue_before"] is not None
    assert event["queue_after"] is not None
    assert event["verdict"] in {"improved", "worse", "neutral", "rejected"}
    assert "关窗" in event["summary"]
