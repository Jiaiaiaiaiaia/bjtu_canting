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
