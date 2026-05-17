import json, pytest
from app import create_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    import api.routes as r
    monkeypatch.setattr(r, "DB_PATH", str(tmp_path / "t.db"))
    app = create_app(); app.config.update(TESTING=True)
    return app.test_client()

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
