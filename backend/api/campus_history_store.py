"""SQLite-backed campus history persistence helpers."""

import json
import sqlite3


def flush_campus_snapshots(db_path: str, snapshot_buffer: list[dict]) -> list[dict]:
    if not snapshot_buffer:
        return snapshot_buffer
    campus_snapshots = [s for s in snapshot_buffer if "campus_totals" in s]
    if not campus_snapshots:
        return snapshot_buffer
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """INSERT INTO campus_snapshot
               (config_id, current_time, campus_totals_json, canteens_json,
                in_transit_json, interventions_json, event_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    s["config_id"],
                    s["current_time"],
                    json.dumps(s["campus_totals"], ensure_ascii=False),
                    json.dumps(s["canteens"], ensure_ascii=False),
                    json.dumps(s["in_transit"], ensure_ascii=False),
                    json.dumps(s.get("interventions", []), ensure_ascii=False),
                    s["event_type"],
                )
                for s in campus_snapshots
            ],
        )
        conn.commit()
    return [s for s in snapshot_buffer if "campus_totals" not in s]


def load_campus_history_rows(db_path: str, config_id: int | None = None) -> list[dict]:
    query = """SELECT s.id, s.config_id, s.current_time AS current_time,
                      s.campus_totals_json, s.canteens_json,
                      s.in_transit_json, s.interventions_json, s.event_type
               FROM campus_snapshot s"""
    params = ()
    if config_id is not None:
        query += " WHERE s.config_id = ?"
        params = (config_id,)
    query += " ORDER BY s.current_time"

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    history = []
    for row in rows:
        item = dict(row)
        item["campus_totals"] = json.loads(item.pop("campus_totals_json") or "{}")
        item["canteens"] = json.loads(item.pop("canteens_json") or "{}")
        item["in_transit"] = json.loads(item.pop("in_transit_json") or "[]")
        item["interventions"] = json.loads(item.pop("interventions_json") or "[]")
        history.append(item)
    return history


def list_campus_history_configs(db_path: str) -> list[dict]:
    query = (
        """SELECT c.id, c.window_count, c.seat_count, c.avg_serve_time,
                  c.avg_eat_time, c.arrival_rate, c.total_time, c.mode,
                  c.created_at, c.campus_config_json
           FROM simulation_config c
           WHERE c.mode = 'campus'
           ORDER BY c.created_at DESC"""
    )
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()

    configs = []
    for row in rows:
        item = dict(row)
        history = load_campus_history_rows(db_path, item["id"])
        totals = [snap["campus_totals"] for snap in history]
        item["snapshot_count"] = len(history)
        item["total_arrived"] = (
            max((t.get("total_arrived", 0) for t in totals), default=None)
        )
        item["total_served"] = (
            max((t.get("total_served", 0) for t in totals), default=None)
        )
        if item.get("campus_config_json"):
            item["campus_config"] = json.loads(item.pop("campus_config_json"))
        configs.append(item)
    return configs


def campus_history_snapshots(
    db_path: str,
    config_id: int,
    snapshot_buffer: list[dict],
) -> list[dict]:
    snapshots = []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """SELECT s.current_time, s.campus_totals_json
               FROM campus_snapshot s
               WHERE s.config_id = ?
               ORDER BY s.current_time""",
            (config_id,),
        ).fetchall()
    for current_time, totals_json in rows:
        snapshots.append({
            "current_time": current_time,
            "campus_totals": json.loads(totals_json or "{}"),
        })

    for item in snapshot_buffer:
        if item.get("config_id") == config_id and "campus_totals" in item:
            snapshots.append({
                "current_time": item["current_time"],
                "campus_totals": item["campus_totals"],
            })

    snapshots.sort(key=lambda s: s["current_time"])
    return snapshots


def campus_history_for_analysis(
    db_path: str,
    config_id: int,
    snapshot_buffer: list[dict],
) -> list[dict]:
    history = load_campus_history_rows(db_path, config_id)

    for item in snapshot_buffer:
        if item.get("config_id") == config_id and "campus_totals" in item:
            buffered = dict(item)
            buffered.setdefault("id", None)
            history.append(buffered)

    seen = set()
    deduped = []
    for snap in history:
        key = (
            snap.get("id"),
            snap.get("current_time"),
            snap.get("event_type"),
            len(snap.get("interventions") or []),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(snap)
    deduped.sort(key=lambda s: (s.get("current_time", 0), s.get("id") or 0))
    return deduped
