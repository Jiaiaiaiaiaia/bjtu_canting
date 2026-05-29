"""迁移守门测试：锁定 src/canteen 包结构关键不变量（spec §6 门 1/2/3/7）。

注意：本文件按其最终位置 tests/ 编写（REPO_ROOT = parents[1]）。
Phase 0 时它仍在 backend/tests/，故必然 RED；Phase 1 移入 tests/ 后转 GREEN。
"""
import re
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]   # tests/ 上一层 = repo 根
SRC = REPO_ROOT / "src"
TESTS = REPO_ROOT / "tests"
BARE_IMPORT = re.compile(r"^\s*(from|import)\s+(api|simulation|app)\b", re.M)


def test_no_bare_api_simulation_app_imports():
    """门 1：src/ 与 tests/ 内不得残留裸 api/simulation/app import（含函数内缩进）。"""
    assert SRC.is_dir(), "src/ 尚不存在（Phase 0 预期 RED）"
    assert TESTS.is_dir(), "tests/ 尚不存在（Phase 0 预期 RED）"
    offenders = []
    for base in (SRC, TESTS):
        for py in base.rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            for m in BARE_IMPORT.finditer(text):
                line_no = text[: m.start()].count("\n") + 1
                offenders.append(f"{py.relative_to(REPO_ROOT)}:{line_no}: {m.group(0).strip()}")
    assert not offenders, "残留裸 import：\n" + "\n".join(offenders)


def test_paths_module_points_to_repo_root():
    """门 2：canteen.paths 派生路径指向真实目录。"""
    from canteen.paths import REPO_ROOT as PKG_REPO_ROOT, FRONTEND_ROOT, DATABASE_DIR, DB_PATH
    assert (PKG_REPO_ROOT / "src" / "canteen").is_dir()
    assert FRONTEND_ROOT.is_dir()
    assert DATABASE_DIR == PKG_REPO_ROOT / "database"
    assert DB_PATH == DATABASE_DIR / "simulation.db"


def test_preset_loader_importable():
    """门 3：preset loader 可导入并加载默认单食堂预设。"""
    from canteen.simulation.presets.loader import load_single_canteen_preset
    cfg = load_single_canteen_preset()
    assert cfg


@pytest.mark.parametrize("as_str", [False, True])
def test_init_db_accepts_str_and_path_db_path(tmp_path, monkeypatch, as_str):
    """门 7：DB_PATH 被 monkeypatch 成 Path 或 str 时 init_db() 均成功并落到该位置。

    db 放在不存在的子目录下，顺带验证建库目录（makedirs/mkdir）对两种类型都成立。
    """
    import canteen.api.routes as routes
    db = tmp_path / "sub" / "test.db"
    monkeypatch.setattr(routes, "DB_PATH", str(db) if as_str else db)
    routes.init_db()
    assert db.exists(), "init_db 应在被 monkeypatch 的路径建库"
    with sqlite3.connect(str(db)) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "simulation_config" in tables
