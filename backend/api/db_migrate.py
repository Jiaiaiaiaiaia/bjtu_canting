"""SQLite 数据库迁移：Phase 2 单食堂 → 多食堂模式。

幂等可重入：可在任意时刻调用（空库 / Phase 2 旧库 / 已迁移库），均不抛错、不重复建列。
"""
import sqlite3


def _table_exists(cursor, name: str) -> bool:
    row = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _column_exists(cursor, table: str, column: str) -> bool:
    cols = [r[1] for r in cursor.execute(f"PRAGMA table_info({table})")]
    return column in cols


def migrate(db_path: str) -> None:
    """对 SQLite 数据库做多食堂模式迁移。可重复调用（幂等）。"""
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()

        # A) 旧表 simulation_config 扩展两列；空库时跳过 ALTER。
        if _table_exists(c, "simulation_config"):
            if not _column_exists(c, "simulation_config", "mode"):
                c.execute(
                    "ALTER TABLE simulation_config ADD COLUMN mode TEXT DEFAULT 'single'"
                )
            if not _column_exists(c, "simulation_config", "campus_config_json"):
                c.execute(
                    "ALTER TABLE simulation_config ADD COLUMN campus_config_json TEXT"
                )

        # B) 新表统一用 IF NOT EXISTS，天然幂等。
        c.execute("""CREATE TABLE IF NOT EXISTS campus_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER,
            current_time REAL NOT NULL,
            campus_totals_json TEXT,
            canteens_json TEXT,
            in_transit_json TEXT,
            event_type TEXT,
            FOREIGN KEY (config_id) REFERENCES simulation_config(id)
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS canteen_definition (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            location_x REAL,
            location_y REAL,
            physical_window_count INTEGER,
            active_window_count INTEGER,
            seat_count INTEGER,
            avg_serve_time REAL,
            avg_eat_time REAL,
            arrival_weight REAL,
            typical_wait_seconds REAL,
            notes TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS walking_time (
            from_code TEXT,
            to_code TEXT,
            walk_seconds REAL,
            PRIMARY KEY (from_code, to_code)
        )""")

        # 幂等加 interventions_json 列到 campus_snapshot
        if _table_exists(c, "campus_snapshot") and not _column_exists(
                c, "campus_snapshot", "interventions_json"):
            c.execute("ALTER TABLE campus_snapshot ADD COLUMN interventions_json TEXT")

        conn.commit()
