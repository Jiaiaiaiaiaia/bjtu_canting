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
