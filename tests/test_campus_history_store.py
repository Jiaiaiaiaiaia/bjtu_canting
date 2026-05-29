"""Campus history persistence helper tests."""

import sqlite3

from canteen.api.campus_history_store import (
    campus_history_for_analysis,
    campus_history_snapshots,
    flush_campus_snapshots,
    list_campus_history_configs,
    load_campus_history_rows,
)


def create_campus_snapshot_table(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE campus_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_id INTEGER,
                current_time REAL NOT NULL,
                campus_totals_json TEXT,
                canteens_json TEXT,
                in_transit_json TEXT,
                event_type TEXT,
                interventions_json TEXT
            )"""
        )
        conn.commit()


def create_simulation_config_table(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE simulation_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_count INTEGER NOT NULL,
                seat_count INTEGER NOT NULL,
                avg_serve_time REAL NOT NULL,
                avg_eat_time REAL NOT NULL,
                arrival_rate REAL NOT NULL,
                total_time INTEGER NOT NULL,
                mode TEXT DEFAULT 'single',
                campus_config_json TEXT,
                created_at TEXT
            )"""
        )
        conn.commit()


def make_snapshot(config_id=1, current_time=10, event_type="step"):
    return {
        "config_id": config_id,
        "current_time": current_time,
        "campus_totals": {"total_arrived": 3, "total_in_queue": 2},
        "canteens": {"minghu_xueyi": {"total_in_queue": 2}},
        "in_transit": [{"student_id": 1}],
        "interventions": [{"event_id": 7}],
        "event_type": event_type,
    }


def test_flush_campus_snapshots_persists_json_and_keeps_non_campus_buffer(tmp_path):
    db_path = tmp_path / "test.db"
    create_campus_snapshot_table(db_path)
    single_snapshot = {"config_id": 1, "queue_details": []}

    remaining = flush_campus_snapshots(
        str(db_path),
        [make_snapshot(), single_snapshot],
    )

    assert remaining == [single_snapshot]
    history = load_campus_history_rows(str(db_path), config_id=1)
    assert len(history) == 1
    assert history[0]["campus_totals"] == {"total_arrived": 3, "total_in_queue": 2}
    assert history[0]["canteens"] == {"minghu_xueyi": {"total_in_queue": 2}}
    assert history[0]["in_transit"] == [{"student_id": 1}]
    assert history[0]["interventions"] == [{"event_id": 7}]
    assert history[0]["event_type"] == "step"


def test_campus_history_snapshots_merges_db_and_buffer_for_config(tmp_path):
    db_path = tmp_path / "test.db"
    create_campus_snapshot_table(db_path)
    flush_campus_snapshots(str(db_path), [make_snapshot(config_id=1, current_time=60)])
    buffer = [
        make_snapshot(config_id=2, current_time=1),
        make_snapshot(config_id=1, current_time=30, event_type="intervention"),
    ]

    assert campus_history_snapshots(str(db_path), config_id=1, snapshot_buffer=buffer) == [
        {"current_time": 30, "campus_totals": {"total_arrived": 3, "total_in_queue": 2}},
        {"current_time": 60.0, "campus_totals": {"total_arrived": 3, "total_in_queue": 2}},
    ]


def test_campus_history_for_analysis_adds_buffered_rows_and_sorts(tmp_path):
    db_path = tmp_path / "test.db"
    create_campus_snapshot_table(db_path)
    flush_campus_snapshots(str(db_path), [make_snapshot(config_id=1, current_time=90)])
    buffer = [make_snapshot(config_id=1, current_time=30, event_type="intervention")]

    history = campus_history_for_analysis(str(db_path), config_id=1, snapshot_buffer=buffer)

    assert [snap["current_time"] for snap in history] == [30, 90.0]
    assert history[0]["id"] is None
    assert history[0]["interventions"] == [{"event_id": 7}]
    assert history[1]["id"] == 1


def test_list_campus_history_configs_returns_campus_configs_with_rollups(tmp_path):
    db_path = tmp_path / "test.db"
    create_simulation_config_table(db_path)
    create_campus_snapshot_table(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """INSERT INTO simulation_config
               (id, window_count, seat_count, avg_serve_time, avg_eat_time,
                arrival_rate, total_time, mode, campus_config_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    1, 3, 60, 20, 10, 5, 8, "campus",
                    '{"campus":{"total_students":100}}',
                    "2026-05-18 10:00:00",
                ),
                (
                    2, 1, 20, 15, 8, 2, 4, "single",
                    None,
                    "2026-05-18 11:00:00",
                ),
                (
                    3, 4, 80, 18, 12, 6, 9, "campus",
                    '{"campus":{"total_students":200}}',
                    "2026-05-18 12:00:00",
                ),
            ],
        )
        conn.commit()

    flush_campus_snapshots(
        str(db_path),
        [
            {
                **make_snapshot(config_id=1, current_time=10),
                "campus_totals": {"total_arrived": 5, "total_served": 2},
            },
            {
                **make_snapshot(config_id=1, current_time=20),
                "campus_totals": {"total_arrived": 8, "total_served": 6},
            },
            {
                **make_snapshot(config_id=3, current_time=10),
                "campus_totals": {"total_arrived": 4, "total_served": 3},
            },
        ],
    )

    configs = list_campus_history_configs(str(db_path))

    assert [item["id"] for item in configs] == [3, 1]
    assert configs[0]["snapshot_count"] == 1
    assert configs[0]["total_arrived"] == 4
    assert configs[0]["total_served"] == 3
    assert configs[0]["campus_config"] == {"campus": {"total_students": 200}}
    assert configs[1]["snapshot_count"] == 2
    assert configs[1]["total_arrived"] == 8
    assert configs[1]["total_served"] == 6
    assert configs[1]["campus_config"] == {"campus": {"total_students": 100}}
