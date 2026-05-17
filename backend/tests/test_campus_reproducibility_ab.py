import random

import pytest
import simpy

from simulation.coordinator import CampusCoordinator
from simulation.random_streams import build_random_streams
from simulation.presets.loader import load_single_canteen_preset


def _run(seed):
    cfg = load_single_canteen_preset()["config"]
    streams = build_random_streams(seed)
    coord = CampusCoordinator(simpy.Environment(), cfg,
                              random.Random(seed), random_streams=streams)
    coord.env.run(until=cfg["campus"]["simulation_seconds"])
    served = [s for s in coord.all_students if s.state == "left"]
    return (coord.total_arrived, coord.total_served,
            tuple(round(s.service_time, 6) for s in served), len(served))


def test_single_preset_demo_scale_completes_students():
    *_, n = _run(123)
    assert n > 0  # 根因修验收：retune 后必须真有完成学生（否则复现测试空转）


def test_same_seed_same_streams_semantically_identical():
    a = _run(123); b = _run(123)
    assert a[3] > 0      # 非空，杜绝空转通过
    assert a == b        # 同 seed → 仿真语义完全一致（含 service_time）


# --- §6.2 "not fake animation" 硬验收：同 seed A/B，差异归因于干预而非 RNG ---


def _run_ab(seed, close_at=None):
    """同 seed 跑全程；close_at 指定时在该时刻关闭首个开放窗口（干预）后续跑。

    返回 (campus_totals, 干预条数)。campus_totals 为聚合不变量，
    同 seed + 无干预必须逐字段一致；干预后必须可观测地不同。
    """
    cfg = load_single_canteen_preset()["config"]
    coord = CampusCoordinator(
        simpy.Environment(), cfg,
        random.Random(seed), random_streams=build_random_streams(seed))
    cid = next(iter(coord.canteens))
    sim_s = cfg["campus"]["simulation_seconds"]
    if close_at is None:
        coord.env.run(until=sim_s)
    else:
        coord.env.run(until=close_at)
        for window in [w for w in coord.canteens[cid].windows if w.is_open][:1]:
            coord.toggle_window(cid, window.id, open=False)
        coord.env.run(until=sim_s)
    snap = coord.snapshot()
    return snap["campus_totals"], len(coord.interventions)


def test_intervention_changes_attributable_not_rng():
    base_a = _run_ab(2024)
    base_b = _run_ab(2024)
    assert base_a == base_b                # 无干预 + 同 seed → 逐字段一致
    interv, n = _run_ab(2024, close_at=60)
    assert n >= 1                          # 干预确实发生
    assert interv != base_a                # 差异来自干预，而非随机噪声


def test_different_seeds_diverge():
    """跨 seed 必须发散——防 "无论 seed 结果恒等" 的退化回归
    （同 seed 恒等单独无法捕获这种退化）。"""
    a = _run_ab(123)
    b = _run_ab(456)
    assert a[1] == 0 and b[1] == 0         # 均无干预，差异纯由 seed 驱动
    assert a != b                          # 不同 seed → campus_totals 不同


# --- AUGMENT 1：route-level 锁定 §3.5 修复的真实调用点 /api/campus/config ---
# 后端测试直接传 random_streams=，不经过 submit_campus_config 构造 streams 的
# 实际修复点。此处经 Flask test_client 走 GET /presets/single-canteen →
# POST /config（默认 rng_seed=42 路径，即 §3.5 必须锁定的链路）→
# POST /finish 快进收敛，断言两个全新 app/client 的 /finish campus_totals
# 与 /statistics（含按学生派生的 service/waiting/eating 等）逐字段一致。
# 还原 C1 会在此处被捕获。fixture 完全复刻 test_campus_api.py（含 _session 重置）。


@pytest.fixture
def client(tmp_path, monkeypatch):
    """每个测试使用独立 SQLite 与全新单例 session（镜像 test_campus_api.py）。"""
    db_path = tmp_path / "test.db"
    import api.routes as routes

    monkeypatch.setattr(routes, "DB_PATH", str(db_path))
    monkeypatch.setattr(routes, "_session", {
        "mode": None,
        "engine": None,
        "coordinator": None,
        "config_id": None,
        "is_running": False,
        "snapshot_buffer": [],
    })

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


_STATS_LOCK_KEYS = (
    "total_arrived", "total_served", "avg_waiting_time", "avg_service_time",
    "avg_eating_time", "avg_walk_time", "switch_rate", "peak_queue_length",
    "window_served", "seat_utilization",
)


def _route_driven_single_run(client):
    """走真实 /api/campus/config（默认 rng_seed 路径）→ /finish → /statistics。

    返回 (finish_campus_totals, 锁定用 statistics 子集)。
    """
    pre = client.get("/api/campus/presets/single-canteen").get_json()
    client.post("/api/campus/config", json=pre["config"])      # 默认 rng_seed=42
    client.post("/api/campus/start")
    finish = client.post(
        "/api/campus/finish?display_tick_seconds=600"
    ).get_json()
    stats = client.get("/api/campus/statistics").get_json()
    return (
        finish["campus_totals"],
        {k: stats[k] for k in _STATS_LOCK_KEYS},
    )


def test_route_level_config_call_site_deterministic(client):
    """单次 route 驱动跑：收敛、规模真实（非空转），结果可被锁定。"""
    totals, stats = _route_driven_single_run(client)
    assert totals["total_arrived"] == totals["total_served"]   # /finish 完全收敛
    assert totals["total_served"] > 0                          # 杜绝空转通过
    assert stats["peak_queue_length"] > 0                      # D3：窗口内确有排队


def test_route_level_config_call_site_reproducible(client, tmp_path, monkeypatch):
    """两个全新 app/client、相同 preset、经 /api/campus/config 默认 rng_seed
    路径，/finish campus_totals 与 /statistics 子集必须逐字段一致——
    锁定 §3.5 修复的真实调用点（还原 C1 会在此失败）。"""
    totals_a, stats_a = _route_driven_single_run(client)

    db_path = tmp_path / "test_b.db"
    import api.routes as routes

    monkeypatch.setattr(routes, "DB_PATH", str(db_path))
    monkeypatch.setattr(routes, "_session", {
        "mode": None,
        "engine": None,
        "coordinator": None,
        "config_id": None,
        "is_running": False,
        "snapshot_buffer": [],
    })
    from app import create_app

    app_b = create_app()
    app_b.config["TESTING"] = True
    with app_b.test_client() as client_b:
        totals_b, stats_b = _route_driven_single_run(client_b)

    assert totals_a == totals_b            # 聚合不变量逐字段一致
    assert stats_a == stats_b              # 含按学生派生的 service/waiting/eating
