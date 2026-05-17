"""Campus simulation service helper tests."""

from api.campus_simulation_service import (
    add_window_intervention,
    pause_campus_session,
    reset_campus_session,
    start_campus_session,
    toggle_window_intervention,
)


class FakeCoordinator:
    def __init__(self):
        self.calls = []

    def toggle_window(self, cid, wid, open=True):
        self.calls.append(("toggle", cid, wid, open))

    def add_window(self, cid, floor_id):
        self.calls.append(("add", cid, floor_id))


def test_start_campus_session_marks_session_running():
    session = {"is_running": False}

    response = start_campus_session(session)

    assert session["is_running"] is True
    assert response == {
        "message": "校园联合仿真已启动",
        "mode": "campus",
        "status": "running",
    }


def test_pause_campus_session_stops_running_and_flushes_snapshots():
    session = {"is_running": True}
    calls = []

    response = pause_campus_session(session, flush_snapshots=lambda: calls.append("flush"))

    assert session["is_running"] is False
    assert calls == ["flush"]
    assert response == {"message": "校园联合仿真已暂停", "mode": "campus"}


def test_reset_campus_session_flushes_and_clears_active_state():
    session = {
        "mode": "campus",
        "engine": object(),
        "coordinator": object(),
        "config_id": 9,
        "is_running": True,
        "snapshot_buffer": [{"config_id": 9}],
    }
    calls = []

    response = reset_campus_session(session, flush_snapshots=lambda: calls.append("flush"))

    assert calls == ["flush"]
    assert session == {
        "mode": None,
        "engine": None,
        "coordinator": None,
        "config_id": None,
        "is_running": False,
        "snapshot_buffer": [],
    }
    assert response == {"message": "校园联合仿真已重置", "mode": None}


def test_toggle_window_intervention_records_snapshot_and_flushes():
    coordinator = FakeCoordinator()
    session = {"snapshot_buffer": []}
    state = {"current_time": 12, "campus_totals": {}, "canteens": {}, "in_transit": []}
    calls = []

    result = toggle_window_intervention(
        coordinator,
        session,
        "minghu_xueyi",
        3,
        False,
        snapshot=lambda event_type: {**state, "event_type": event_type},
        compact_snapshot=lambda snap, event_type: {"compact": event_type, "time": snap["current_time"]},
        flush_snapshots=lambda: calls.append("flush"),
    )

    assert coordinator.calls == [("toggle", "minghu_xueyi", 3, False)]
    assert session["snapshot_buffer"] == [{"compact": "intervention", "time": 12}]
    assert calls == ["flush"]
    assert result["event_type"] == "intervention"


def test_add_window_intervention_records_snapshot_and_flushes():
    coordinator = FakeCoordinator()
    session = {"snapshot_buffer": []}
    state = {"current_time": 18, "campus_totals": {}, "canteens": {}, "in_transit": []}
    calls = []

    result = add_window_intervention(
        coordinator,
        session,
        "minghu_xueyi",
        2,
        snapshot=lambda event_type: {**state, "event_type": event_type},
        compact_snapshot=lambda snap, event_type: {"compact": event_type, "time": snap["current_time"]},
        flush_snapshots=lambda: calls.append("flush"),
    )

    assert coordinator.calls == [("add", "minghu_xueyi", 2)]
    assert session["snapshot_buffer"] == [{"compact": "intervention", "time": 18}]
    assert calls == ["flush"]
    assert result["event_type"] == "intervention"
