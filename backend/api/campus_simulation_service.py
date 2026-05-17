"""Session-level service helpers for campus simulation routes."""


def start_campus_session(session: dict) -> dict:
    session["is_running"] = True
    return {
        "message": "校园联合仿真已启动",
        "mode": "campus",
        "status": "running",
    }


def pause_campus_session(session: dict, flush_snapshots) -> dict:
    session["is_running"] = False
    flush_snapshots()
    return {"message": "校园联合仿真已暂停", "mode": "campus"}


def reset_campus_session(session: dict, flush_snapshots) -> dict:
    flush_snapshots()
    session["mode"] = None
    session["engine"] = None
    session["coordinator"] = None
    session["config_id"] = None
    session["is_running"] = False
    session["snapshot_buffer"] = []
    return {"message": "校园联合仿真已重置", "mode": None}


def _record_intervention(session: dict, snapshot, compact_snapshot, flush_snapshots) -> dict:
    state = snapshot("intervention")
    session["snapshot_buffer"].append(compact_snapshot(state, "intervention"))
    flush_snapshots()
    return state


def toggle_window_intervention(
    coordinator,
    session: dict,
    cid,
    wid,
    open_,
    snapshot,
    compact_snapshot,
    flush_snapshots,
) -> dict:
    coordinator.toggle_window(cid, wid, open=open_)
    return _record_intervention(session, snapshot, compact_snapshot, flush_snapshots)


def add_window_intervention(
    coordinator,
    session: dict,
    cid,
    floor_id,
    snapshot,
    compact_snapshot,
    flush_snapshots,
) -> dict:
    coordinator.add_window(cid, floor_id)
    return _record_intervention(session, snapshot, compact_snapshot, flush_snapshots)
