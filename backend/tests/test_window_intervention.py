import simpy
from simulation.canteen import Canteen

DEF = {"id": "c", "display_name": "C", "campus_position": {"x":0,"y":0},
       "avg_serve_time_seconds": 10, "avg_eat_time_minutes": 5,
       "arrival_weight": 1.0, "typical_wait_seconds": 0.0,
       "floors": [{"floor_id": 1,
                   "windows": {"physical_count": 5, "active_count": 3},
                   "seats": {"count": 10}}]}

def _canteen():
    return Canteen(simpy.Environment(), DEF)

def test_all_physical_windows_instantiated():
    c = _canteen()
    assert len(c.windows) == 5
    assert sum(w.is_open for w in c.windows) == 3
    assert c.open_window_count == 3
    assert c.active_window_count == 3

def test_shortest_window_only_open():
    c = _canteen()
    for w in c.windows:
        if w.is_open:
            w.waiting_students.extend([object()] * 9)
    assert c.shortest_window().is_open is True

def test_open_window_capacity_score_excludes_closed():
    c = _canteen()
    assert abs(c.open_window_capacity_score - 3 * (1/10)) < 1e-9


import random
from simulation.coordinator import CampusCoordinator
from simulation.presets.loader import load_single_canteen_preset
from simulation.random_streams import build_random_streams


def _coord():
    cfg = load_single_canteen_preset()["config"]
    return CampusCoordinator(simpy.Environment(), cfg,
        random.Random(1), random_streams=build_random_streams(1))

def test_toggle_close_then_open_idempotent_and_event_logged():
    co = _coord(); cid = next(iter(co.canteens)); c = co.canteens[cid]
    w = next(w for w in c.windows if w.is_open)
    r1 = co.toggle_window(cid, w.id, open=False)
    assert r1["status"] == "applied" and w.is_open is False
    r2 = co.toggle_window(cid, w.id, open=False)   # 重复关
    assert r2["status"] == "applied"               # idempotent 返回
    assert co.toggle_window(cid, w.id, open=True)["status"] == "applied"
    assert w.is_open is True
    assert any(e["action"] in ("open","close") for e in co.interventions)

def test_cannot_close_last_open_window():
    co = _coord(); cid = next(iter(co.canteens)); c = co.canteens[cid]
    opened = [w for w in c.windows if w.is_open]
    for w in opened[:-1]:
        co.toggle_window(cid, w.id, open=False)
    last = opened[-1]
    res = co.toggle_window(cid, last.id, open=False)
    assert res["status"] == "rejected" and last.is_open is True
