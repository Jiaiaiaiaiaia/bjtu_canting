# 标准 Python 包结构重构 实施计划（Spec A）

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐步实施。步骤用 checkbox（`- [ ]`）跟踪。
> 配套设计：`docs/superpowers/specs/2026-05-28-standard-package-restructure-design.md`（含 7 道验收门、范围边界、证据）。

**Goal:** 把后端从 `backend/` 扁平布局迁移为标准 `src/canteen/` 包（`pyproject.toml` + editable install），不破坏任何对外 API、保持 `frontend/` 原名、每个 commit 可跑可回退。

**Architecture:** 三阶段——Phase 0 先写迁移守门测试并确认 RED（不提交）；Phase 1 原子完成"建包 + 移动 + import 改写 + 路径中心化"，7 道门全绿后**单次提交**（守门测试与实现一起）；Phase 2 同步文档/命令。新增 `canteen.paths` 作为 repo-root 派生路径的唯一真相源；绝对 import 全部加 `canteen.` 前缀，包内相对 import 不变。

**Tech Stack:** Python 3.10+、setuptools（src-layout）、Flask、SimPy、pytest、`rg`/`perl`（批量改写）、`node --check`（JS 语法）。

**分支:** `restructure/standard-package`（已创建）。

---

## 范围边界（本计划严格不做，留 Spec B）

- 不移动 `docs/superpowers/`、`task_plan.md`、`progress.md`、`findings.md`、`reviews/`（`AGENTS.md:31-34` 引用它们）。
- 不移动 `gen_docs.py`、不合并 `agent.md`、不拆分前端大文件。
- 不改名 `frontend/`。
- 不动 `.worktrees/3d-canteen-digital-twin/` 内的平行 `backend/` 树（独立 worktree，迁移只动主树）。

---

## 文件结构（迁移后）

| 文件 | 责任 | 动作 |
|------|------|------|
| `pyproject.toml` | 打包元数据、依赖、src-layout 包发现、presets package-data、pytest testpaths | 新建 |
| `conftest.py`（repo 根） | 把 `src/` 注入 sys.path，免安装也能 pytest | 新建 |
| `requirements.txt` | 指向 `-e .` | 改写 |
| `src/canteen/__init__.py` | 包根 | 新建（空） |
| `src/canteen/paths.py` | repo-root 派生路径单一真相源 | 新建 |
| `src/canteen/__main__.py` | `python -m canteen` 入口（5001） | 新建 |
| `src/canteen/app.py` | Flask 工厂；路径取自 `canteen.paths` | ← `backend/app.py`，改 |
| `src/canteen/api/` | API 蓝图、DB、迁移 | ← `backend/api/`，改 import |
| `src/canteen/api/routes.py` | 单食堂 API；`DB_PATH` 取自 `canteen.paths` | 改 |
| `src/canteen/api/campus_routes.py` | campus API；`import canteen.api.routes as single_routes` | 改 |
| `src/canteen/simulation/` | 仿真核心 | ← `backend/simulation/`，改 import |
| `src/canteen/simulation/presets/__init__.py` | 让 presets 成为正规子包（find + package-data 可靠） | 新建（空） |
| `tests/` | 全部 pytest | ← `backend/tests/`，改 import + `parents[2]→[1]` |
| `tests/test_package_migration_guard.py` | 迁移守门（门 1/2/3/7） | 新建（Phase 0） |

---

## Task 1 — Phase 0：守门测试先行（RED，**不提交**）

**Files:**
- Create: `backend/tests/test_package_migration_guard.py`（暂放当前测试目录，Phase 1 随 `git mv` 一起进 `tests/`）

> 参见 @superpowers:test-driven-development：先写测试，确认失败，再实现。本任务结束**不提交**——避免提交红测试违背"每个 commit 可跑"。

- [ ] **Step 1-1: 写守门测试文件**

```python
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
```

- [ ] **Step 1-2: 运行，确认全 RED 并记录**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/test_package_migration_guard.py -v
```
Expected（Phase 0）：4 项全部 FAIL —
- `test_no_bare_...` → AssertionError（`src/` 不存在）
- 其余 3 项 → `ModuleNotFoundError: No module named 'canteen'`

记录这些预期失败。**不要 commit。**

---

## Task 2 — Phase 1：原子建包（7 门全绿后**单次提交**）

**Files:** 见上文文件结构表。本任务一气呵成；中途 tree 会处于 RED，属预期，**仅在 Step 2-13 全绿后提交一次**。

### 2A 脚手架（新增文件，加性）

- [ ] **Step 2-1: 建 `src/canteen/paths.py`**

```python
"""repo-root 派生路径的唯一真相源（spec §5.1）。"""
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent       # .../src/canteen
REPO_ROOT = PACKAGE_ROOT.parents[1]                  # parents[0]=src, parents[1]=repo 根
FRONTEND_ROOT = REPO_ROOT / "frontend"
DATABASE_DIR = REPO_ROOT / "database"
DB_PATH = DATABASE_DIR / "simulation.db"
```

- [ ] **Step 2-2: 建 `src/canteen/__init__.py`（空文件）与 `src/canteen/__main__.py`**

`src/canteen/__init__.py`：空。

`src/canteen/__main__.py`：
```python
"""python -m canteen → 启动开发服务器（保留旧 5001 端口体验）。"""
from canteen.app import create_app

create_app().run(host="0.0.0.0", port=5001, debug=True)
```

- [ ] **Step 2-3: 建 `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=64"]
build-backend = "setuptools.build_meta"

[project]
name = "canteen"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "flask>=3.0.0",
    "flask-cors>=4.0.0",
    "simpy>=4.1.1",
]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"canteen.simulation.presets" = ["*.json"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2-4: 建 repo 根 `conftest.py`**

```python
"""把 src/ 注入 sys.path，未 pip install -e . 也能 import canteen.*。
pytest 无条件先收集 repo 根 conftest（不受 testpaths 限制），故对 tests/ 全量生效。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
```

- [ ] **Step 2-5: 改 `requirements.txt` 为 editable 安装**

整文件替换为：
```
-e .
```

### 2B 移动（git mv）

- [ ] **Step 2-6: 移动后端代码与测试**

```bash
git mv backend/api src/canteen/api
git mv backend/simulation src/canteen/simulation
git mv backend/app.py src/canteen/app.py
git mv backend/tests tests
```

- [ ] **Step 2-7: 把 Phase 0 的未跟踪守门测试带入 `tests/`，建 presets 子包 init**

```bash
# git mv 只搬已跟踪文件；Phase 0 的守门测试未跟踪，需手动搬
[ -f backend/tests/test_package_migration_guard.py ] && \
  mv backend/tests/test_package_migration_guard.py tests/
# presets 当前无 __init__.py（命名空间子包）；建正规子包让 find+package-data 可靠
touch src/canteen/simulation/presets/__init__.py
# 清理可能残留的空目录/缓存
rm -rf backend/__pycache__ backend/tests 2>/dev/null
rmdir backend 2>/dev/null || true
```

Run（确认 backend 已清空）：`ls backend 2>/dev/null || echo "backend gone"`
Expected：`backend gone`

### 2C import 改写（perl，作用于 src/ 与 tests/）

- [ ] **Step 2-8: 批量改写绝对 import（每条只跑一次，避免二次加前缀）**

```bash
PYFILES=$(find src tests -name '*.py')
perl -pi -e '
  s/\bfrom simulation\b/from canteen.simulation/g;
  s/\bimport simulation\b/import canteen.simulation/g;
  s/\bfrom api\b/from canteen.api/g;
  s/\bimport api\b/import canteen.api/g;
  s/\bfrom app\b/from canteen.app/g;
' $PYFILES
```
覆盖：`from simulation.X` / `from simulation import` / `import simulation.X as` / `from api.X` / `from api import` / `import api.routes as` / `from app import`。包内相对 `from .x` 不被触及（不以 `from simulation/api/app` 开头）。词边界 `\b` 不误伤 `apiclient`/`application`。

- [ ] **Step 2-9: 批量改测试路径锚点 `parents[2]→parents[1]`（共 9 处）**

```bash
perl -pi -e 's/\.parents\[2\]/.parents[1]/g' $(find tests -name '*.py')
```
Run（确认无残留）：`rg -n "parents\[2\]" tests || echo "no parents[2] left"`
Expected：`no parents[2] left`

- [ ] **Step 2-10: 删除旧 `tests/conftest.py` 的 backend 注入逻辑**

`tests/conftest.py`（原 `backend/tests/conftest.py`）当前仅注入 `BACKEND_ROOT`，已被 repo 根 `conftest.py` 注入 `src/` 取代 → 整文件替换为最小内容（或删除）。建议替换为：
```python
"""测试公共配置：包路径注入已上移至 repo 根 conftest.py（注入 src/）。"""
```

### 2D 路径中心化（显式编辑）

- [ ] **Step 2-11: 改 `src/canteen/app.py`**

整文件替换为（删 `sys.path` hack 与 `os/sys` 依赖，路径取自 `canteen.paths`；注意 Step 2-8 已把 `from api...` 改成 `from canteen.api...`，此处给出最终态）：
```python
"""Flask 入口。"""
from flask import Flask, render_template
from flask_cors import CORS

from canteen.api import api_bp, init_db
from canteen.api.campus_routes import campus_bp
from canteen.paths import FRONTEND_ROOT


def create_app():
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_ROOT / 'templates'),
        static_folder=str(FRONTEND_ROOT / 'static'),
        static_url_path='/static',
    )
    CORS(app)
    init_db()
    app.register_blueprint(api_bp)
    app.register_blueprint(campus_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    return app


if __name__ == '__main__':
    create_app().run(host='0.0.0.0', port=5001, debug=True)
```

- [ ] **Step 2-12: 改 `src/canteen/api/routes.py` 的 DB_PATH**

删除原 `DB_PATH = os.path.join(os.path.dirname(...×3), 'database', 'simulation.db')` 整块（约 14-18 行），改为从 `canteen.paths` 导入。在文件顶部 import 区（`from canteen.simulation import SimulationEngine` 附近）加：
```python
from canteen.paths import DB_PATH
```
**保持** `init_db()` 内 `os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)` **不变**——`os.path.dirname` 接受 path-like，对 `Path`（默认）与 `str`（测试 monkeypatch）都正确（spec §5.1，**禁止**改成裸 `DB_PATH.parent`）。`import os` 仍被该行使用，保留。

> 检查：`src/canteen/api/__init__.py` 为 `from .routes import api_bp, init_db`（相对 import，不改），故 `from canteen.api import api_bp, init_db` 可用。`campus_routes.py:9` 已被 Step 2-8 改为 `import canteen.api.routes as single_routes`，与 routes 共享同一 `_session`/`DB_PATH` 实例。

### 2E 安装、验收门、提交

- [ ] **Step 2-13a: 人工审阅改动**

```bash
git status
git diff -- src tests | head -200
```
确认：无 `from canteen.canteen`（二次加前缀）、无被误改的 JS 字符串字面量、`frontend/` 路径字面量未变。

- [ ] **Step 2-13b: editable 安装**

```bash
./.venv/bin/pip install -e .
```
Expected：成功安装 `canteen-0.1.0`，无报错。

- [ ] **Step 2-13c: 跑 7 道验收门**

```bash
# 门 1/2/3/7 守门测试 + 门 4 全套
./.venv/bin/python -m pytest tests -q
# 门 1 命令式复核：必须无输出
rg -n "^\s*(from|import)\s+(api|simulation|app)\b" src tests || echo "GATE1 OK: no bare imports"
# 门 3 preset loader 冒烟
./.venv/bin/python -c "from canteen.simulation.presets.loader import load_single_canteen_preset; load_single_canteen_preset(); print('GATE3 OK')"
# 门 5 起服（后台启动→探活→关闭）
./.venv/bin/python -m canteen & SRV=$!; sleep 3; \
  curl -fs -o /dev/null -w "GATE5 HTTP %{http_code}\n" http://127.0.0.1:5001/ ; kill $SRV
```
Expected：
- `pytest tests -q` 全 PASS，用例数 ≥ 迁移前基线（迁移前：`PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q`）。
- `GATE1 OK: no bare imports`
- `GATE3 OK`
- `GATE5 HTTP 200`

- [ ] **Step 2-13d: 门 6 浏览器冒烟（人工）**

浏览器开 `http://127.0.0.1:5001/`，走 config→start→run→finish→统计/历史；控制台 0 error；3D canvas 非空。记录结果。

- [ ] **Step 2-13e: 全绿后单次提交（守门测试 + 实现）**

```bash
git add -A -- src tests pyproject.toml conftest.py requirements.txt
git status   # 复核暂存内容，确认未误加范围外文件
git commit -m "refactor(pkg): 迁移 backend/ → src/canteen 标准包（paths 中心化 + import 改写 + tests 上移）"
```

> 回退：本提交是单个原子提交，`git revert <hash>` 即回到 `backend/` 布局。

---

## Task 3 — Phase 2：文档/命令同步（绿，提交）

**Files:**
- Modify: `README.md`、`AGENTS.md`、`agent.md`、`CLAUDE.md`

> `AGENTS.md:7` 要求 `agent.md`/`CLAUDE.md` 在广义协作规则变化时保持同步——三份的"常用命令/验证"段一并改。

- [ ] **Step 3-1: 统一新命令**

旧 → 新 映射（四份文档中凡出现处）：
| 旧 | 新 |
|----|----|
| `./.venv/bin/pip install -r requirements.txt` | 不变（内容已是 `-e .`）；或显式 `./.venv/bin/pip install -e .` |
| `PYTHONPATH=backend ./.venv/bin/python backend/app.py` | `./.venv/bin/python -m canteen`（或 `./.venv/bin/flask --app canteen.app run -p 5001`，**必须显式 `-p 5001`**，否则默认 5000） |
| `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q` | `./.venv/bin/python -m pytest tests -q` |
| `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_engine.py -q` | `./.venv/bin/python -m pytest tests/test_engine.py -q` |

- [ ] **Step 3-2: 同步目录结构描述**

`README.md`「目录结构」、`agent.md`/`CLAUDE.md`「项目结构」、`AGENTS.md` 内对 `backend/...` 的路径描述更新为 `src/canteen/...`、`tests/`。
**不改** `AGENTS.md:31-34` 对 `docs/superpowers/*` 与 `task_plan/progress/findings.md` 的引用（它们未移动，引用仍有效）。
`node --check` 等前端校验命令中的 `frontend/static/...` 路径**不变**（`frontend/` 保留原名）。

- [ ] **Step 3-3: 复跑验证命令确认文档可用**

```bash
./.venv/bin/python -m pytest tests -q
./.venv/bin/python -m canteen & SRV=$!; sleep 3; curl -fs -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5001/; kill $SRV
```
Expected：测试全绿；HTTP 200。

- [ ] **Step 3-4: 提交**

```bash
git add -- README.md AGENTS.md agent.md CLAUDE.md
git commit -m "docs: 同步运行/验证命令与目录结构到 src/canteen 包布局"
```

---

## 验收总览（对应 spec §6）

| 门 | 内容 | 验证 |
|----|------|------|
| 1 | 裸 import 清零（含 app、缩进） | `rg -n "^\s*(from\|import)\s+(api\|simulation\|app)\b" src tests` 空 + 守门测试 |
| 2 | paths 中心化指向 repo 根 | `test_paths_module_points_to_repo_root` |
| 3 | preset loader 可用 | `test_preset_loader_importable` + 冒烟 |
| 4 | 全套测试绿、用例数不减 | `pytest tests -q` |
| 5 | `python -m canteen` 起服 5001 | curl HTTP 200 |
| 6 | 浏览器端到端 0 error | 人工冒烟 |
| 7 | DB_PATH str/Path monkeypatch 兼容 | `test_init_db_accepts_str_and_path_db_path`（参数化 Path/str） |
