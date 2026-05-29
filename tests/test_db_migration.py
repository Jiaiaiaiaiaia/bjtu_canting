"""数据库迁移脚本单元测试 —— 验证 Phase 2 旧库平滑升级到多食堂模式。"""
import sqlite3

from canteen.api.db_migrate import migrate


def test_alter_simulation_config_adds_mode_column(tmp_path):
    db = str(tmp_path / "t.db")
    # 模拟 Phase 2 旧表
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE simulation_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            window_count INTEGER, seat_count INTEGER,
            avg_serve_time REAL, avg_eat_time REAL,
            arrival_rate REAL, total_time INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
    migrate(db)
    with sqlite3.connect(db) as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(simulation_config)")]
    assert "mode" in cols
    assert "campus_config_json" in cols


def test_creates_campus_snapshot_table(tmp_path):
    db = str(tmp_path / "t.db")
    migrate(db)
    with sqlite3.connect(db) as c:
        rows = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='campus_snapshot'"
        ).fetchall()
    assert len(rows) == 1


def test_old_history_query_still_works(tmp_path):
    """Phase 2 兼容回归：迁移后 simulation_snapshot 旧表仍可查。"""
    db = str(tmp_path / "t.db")
    # 模拟 Phase 2 init_db 后的 schema：simulation_config + simulation_snapshot
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE simulation_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            window_count INTEGER, seat_count INTEGER,
            avg_serve_time REAL, avg_eat_time REAL,
            arrival_rate REAL, total_time INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE simulation_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER, current_time REAL NOT NULL,
            total_arrived INTEGER, total_served INTEGER,
            total_in_queue INTEGER, total_eating INTEGER,
            empty_seats INTEGER, queue_details TEXT, event_type TEXT
        )""")
        c.execute("INSERT INTO simulation_config (window_count, seat_count, avg_serve_time, avg_eat_time, arrival_rate, total_time) VALUES (6, 200, 30, 15, 5, 60)")
        c.execute("INSERT INTO simulation_snapshot (config_id, current_time, total_arrived) VALUES (1, 100, 50)")
    migrate(db)
    with sqlite3.connect(db) as c:
        rows = c.execute("SELECT total_arrived FROM simulation_snapshot WHERE config_id=1").fetchall()
    assert rows == [(50,)]


def test_alter_preserves_existing_phase2_rows(tmp_path):
    """迁移后 Phase 2 旧行数据完整，新列默认值正确。"""
    db = str(tmp_path / "t.db")
    # 模拟 Phase 2 旧表，并插入一条数据
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE simulation_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            window_count INTEGER, seat_count INTEGER,
            avg_serve_time REAL, avg_eat_time REAL,
            arrival_rate REAL, total_time INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("INSERT INTO simulation_config (window_count, seat_count, avg_serve_time, avg_eat_time, arrival_rate, total_time) VALUES (6, 200, 30, 15, 5, 60)")

    # 迁移
    migrate(db)

    # 验证：老数据未丢失，新列默认值正确
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT window_count, seat_count, mode FROM simulation_config WHERE id=1").fetchone()
    assert row == (6, 200, "single")


def test_migrate_is_idempotent_when_called_twice(tmp_path):
    """连续两次 migrate 不应抛异常，也不重复 ALTER。"""
    db = str(tmp_path / "t.db")
    # 模拟 Phase 2 旧表
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE simulation_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            window_count INTEGER, seat_count INTEGER,
            avg_serve_time REAL, avg_eat_time REAL,
            arrival_rate REAL, total_time INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
    # 第 1 次：把 db 迁到新 schema
    migrate(db)
    # 第 2 次：不应抛
    migrate(db)
    # 验证列依然只加了一遍（不是两个 mode 列等）
    with sqlite3.connect(db) as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(simulation_config)")]
    assert cols.count("mode") == 1
    assert cols.count("campus_config_json") == 1


def test_interventions_json_column_idempotent(tmp_path):
    """campus_snapshot 幂等加 interventions_json 列。"""
    db = str(tmp_path / "t.db")
    migrate(db)
    migrate(db)  # 重入幂等
    with sqlite3.connect(db) as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(campus_snapshot)")]
    assert "interventions_json" in cols
