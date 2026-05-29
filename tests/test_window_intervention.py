import random

import simpy
from canteen.simulation.canteen import Canteen
from canteen.simulation.coordinator import CampusCoordinator
from canteen.simulation.presets.loader import load_single_canteen_preset
from canteen.simulation.random_streams import build_random_streams
from canteen.simulation.student import Student

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


def test_add_window_creates_open_physical_window_on_floor():
    c = _canteen()
    before_physical = c.physical_window_count
    before_open = c.open_window_count

    window = c.add_window(floor_id=1)

    assert window.id == max(w.id for w in c.windows)
    assert window.floor_id == 1
    assert window.is_open is True
    assert c.windows[-1] is window
    assert c.physical_window_count == before_physical + 1
    assert c.open_window_count == before_open + 1


def test_snapshot_exposes_window_open_and_closing_state():
    c = _canteen()
    w = c.windows[0]
    w.is_open = False
    w.join_queue(Student(id=99, state="queueing"))

    snap = c.snapshot()
    flat = next(item for item in snap["windows"] if item["id"] == w.id)
    nested = next(
        item for floor in snap["floors"]
        for item in floor["windows"]
        if item["id"] == w.id
    )

    assert flat["is_open"] is False
    assert flat["closing"] is True
    assert nested["is_open"] is False
    assert nested["closing"] is True


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
