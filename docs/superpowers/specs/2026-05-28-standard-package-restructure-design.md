# 标准 Python 包结构重构 — 设计文档（Spec A）

> **Date:** 2026-05-28
> **Status:** Approved for spec review
> **Branch:** `restructure/standard-package`
> **For agentic workers:** 本文件是设计 spec，不是实施计划。实施计划由后续 `writing-plans` 生成。

---

## 0. 范围声明（最重要，先读）

**本 Spec 只做一件事：把后端从 `backend/` 扁平布局迁移为标准 Python `src/` 包布局（`src/canteen/`）。**

**本 Spec 明确不做**（全部留给后续 **Spec B**）：

- 不重排 `docs/` 体系（`docs/superpowers/`、`docs/phase2`、`docs/phase3` 一律不动）。
- 不移动 `gen_docs.py`（留在根目录）。
- 不合并 `agent.md` / `AGENTS.md` / `CLAUDE.md`（仅在 Phase 2 同步其中的运行命令文本）。
- 不拆分前端大文件（`canteen_scene.js`、`state_adapter.js`、`main.js`、`analysis_charts.js`、`style.css`）。
- 不移动 `task_plan.md` / `progress.md` / `findings.md` / `reviews/`。

理由：`AGENTS.md:31-34` 把 `docs/superpowers/specs|plans/*` 与根目录 `task_plan.md / progress.md / findings.md` 作为协作守门引用；移动它们会从"代码结构重构"退化成"协作规则重构"，扩大风险面。本 Spec 保持这些路径不变，专注 Python 包结构。

---

## 1. 背景与目标

- **项目**：北京交通大学就餐仿真系统（Flask + SimPy + SQLite + 原生 JS/ECharts/Three.js）。
- **现状**：后端在 `backend/{api,simulation}`，靠 `PYTHONPATH=backend`（及 `app.py` 里的 `sys.path.insert`）运行；import 混用"绝对（根在 `backend/`）"与"包内相对"。
- **目标**：升级为标准 `src/canteen/` 包 + `pyproject.toml`，可 `pip install -e .`；运行/测试命令规范化；**全程可回退、可验证、低误伤**。
- **野心档位**：用户在三档（原地整理 / 整理+后端分层 / 标准包重构）中选择**标准包重构**，并接受运行命令变更、单人开发、无演示/交付即时约束。

---

## 2. 约束与不变量

1. **API 兼容基线不破坏**：`/api/config`、`/api/simulation/*`、`/api/campus/*` 的蓝图、URL 前缀、响应形状不变（仅改 import 路径，逻辑零改动）。来源：`CLAUDE.md`、`AGENTS.md:23-26`。
2. **每个 git commit 必须可跑、可回退**：phase 内不留半成品提交。
3. **`frontend/` 保留原名**：`backend/tests/test_frontend_three_js_contract.py`（3583 行）内有数十处 `'./frontend/static/js/...'` 字符串字面量断言；改名 = 纯 churn、零功能收益。Flask 路径在 `app.py` 计算，保留原名最稳。
4. **协作守门路径不动**：见 §0。
5. **前端零改**：`index.html` 全部用 `url_for('static', filename=...)`，`static_url_path='/static'` 不变，故 HTML / JS / importmap 不需改动。

---

## 3. 现状关键事实（带证据，迁移设计的依据）

| 事实 | 证据 | 迁移影响 |
|------|------|---------|
| 运行入口是工厂函数 + sys.path hack | `backend/app.py:15` `create_app()`；`:9` `sys.path.insert(0, backend_dir)` | 包化后删 hack，改用 editable install |
| 模板/静态路径从 repo 根算 | `backend/app.py:16` `project_root = dirname(dirname(__file__))` = repo 根 | 移到 `src/canteen/app.py` 后 `dirname×2` 指向 `src/`，**会坏** → 中心化 |
| DB 路径从 repo 根算 | `backend/api/routes.py:14-16` `DB_PATH = dirname×3(__file__) + 'database'` = repo 根 | 移到 `src/canteen/api/routes.py` 后指向 `src/`，**会坏** → 中心化 |
| campus 复用单食堂模块的全局态 | `backend/api/campus_routes.py:9` `import api.routes as single_routes`；用 `single_routes._session`(:42) 与 `single_routes.DB_PATH`(:73,79,84,92) | 裸 import 残留 = `_session` 分裂成两个模块实例，单食堂/campus 看到不同会话 → **裸 import 必须清零** |
| presets 相邻读取 | `backend/simulation/presets/loader.py:8` `PRESET_DIR = Path(__file__).resolve().parent`；`CANTEEN_FILES = (...json)` | 随包移动透明；标准包需声明 package-data |
| import 两套且含函数内缩进 import | 绝对：`from simulation.X`、`from api.X`、`import api.routes as routes`（部分在函数体内缩进）；相对：`from .student`、`from .db_migrate` 等 | 绝对 import 全部改写；**相对 import 不变**；检查正则必须能抓缩进 import |
| 前端引用与 import map 走 url_for | `frontend/templates/index.html` 全用 `url_for('static', ...)`；importmap 同理 | 前端零改 |
| 测试 repo-root 锚点（分散在各测试文件，**非 conftest**） | 7 个 `*_contract.py` 用 `REPO_ROOT = Path(__file__).resolve().parents[2]` = repo 根；`test_twin_visual_assets_contract.py:2-3` 用 `ROOT = parents[2]` + `VENDOR = ROOT/'frontend/static/js/three/vendor'` | 测试上移一层后 `parents[2]→parents[1]` |
| `backend/tests/conftest.py`（仅注入路径，8 行） | 仅 `BACKEND_ROOT = dirname×2(__file__)`（=`backend/`）插入 sys.path 以便 `import simulation/api/app`；**不含** ROOT/VENDOR | 随 repo 根 `conftest.py` 注入 `src/` 而冗余 → 删除该注入逻辑 |
| 测试用 monkeypatch 重定向 DB 写入 | 4 文件 `monkeypatch.setattr(routes, "DB_PATH", str(db_path))`（`test_api.py:10`、`test_campus_api.py:14`、`test_campus_intervention_api.py:10`、`test_campus_reproducibility_ab.py:92,152`） | `init_db()` 目录创建须 `str`/`Path` 双兼容（见 §5.1、§6 门 7） |
| 依赖 | `requirements.txt`: `flask>=3.0.0`、`flask-cors>=4.0.0`、`simpy>=4.1.1` | 写入 `pyproject` `[project.dependencies]` |
| `gen_docs.py` 无代码耦合 | 全仓库无 import 引用；内部 `'simulation/engine.py'` 等仅为报告文字，非文件读取 | 本 Spec 不动它（留根目录） |

---

## 4. 目标结构

```
Canteen/
├─ pyproject.toml              # 新增：依赖 + src-layout + presets package-data + pytest 配置
├─ conftest.py                 # 新增（repo 根）：注入 src/ → 免安装也能 pytest
├─ requirements.txt            # 改为 `-e .`（保持 pip install -r requirements.txt 可用）
├─ src/
│  └─ canteen/
│     ├─ __init__.py           # 新增
│     ├─ __main__.py           # 新增：python -m canteen → create_app().run(port=5001)
│     ├─ paths.py              # 新增：repo-root 派生路径的唯一真相源
│     ├─ app.py                # ← backend/app.py（删 sys.path hack；路径取自 paths.py）
│     ├─ api/                  # ← backend/api/（包内相对 import 不变；绝对 import 改写）
│     └─ simulation/           # ← backend/simulation/（含 presets/*.json）
├─ tests/                      # ← backend/tests/（绝对 import 改写；parents[2]→[1]；conftest 改）
│  └─ conftest.py
├─ frontend/                   # 原名不动（templates/ static/）
├─ database/                   # 运行时 SQLite（.gitignore，不动）
├─ docs/                       # 完全不动（含 docs/superpowers/）
├─ gen_docs.py                 # 不动
├─ task_plan.md progress.md findings.md reviews/   # 不动
└─ README.md AGENTS.md agent.md CLAUDE.md          # 仅 Phase 2 同步运行命令文本
```

> `src/` 放可导入的 Python 包；`frontend/`、`tests/`、`docs/` 与 `src/` 平级——标准 src-layout。

---

## 5. 设计细节

### 5.1 `src/canteen/paths.py` —— 路径单一真相源

```python
from pathlib import Path

PACKAGE_ROOT  = Path(__file__).resolve().parent   # .../src/canteen
REPO_ROOT     = PACKAGE_ROOT.parents[1]            # .../  (parents[0]=src, parents[1]=repo 根)
FRONTEND_ROOT = REPO_ROOT / "frontend"
DATABASE_DIR  = REPO_ROOT / "database"
DB_PATH       = DATABASE_DIR / "simulation.db"
```

消费方改写：

- `app.py`：`template_folder = str(FRONTEND_ROOT / "templates")`、`static_folder = str(FRONTEND_ROOT / "static")`（替代原 `project_root = dirname×2`）；删除 `sys.path.insert`。
- `api/routes.py`：`from canteen.paths import DB_PATH`（替代原 `dirname×3` 计算）；`os.makedirs(os.path.dirname(DB_PATH), ...)` 等用法不变（`DB_PATH` 改为 `Path` 时需确认 `sqlite3.connect(str(DB_PATH))` 与 `os.path.dirname` 兼容——实施时用 `str()` 包裹或改 `DATABASE_DIR`）。
- `api/campus_routes.py:9`：`import canteen.api.routes as single_routes`（消除裸 import；`_session`/`DB_PATH` 仍走它，**保证单一模块实例**）。

> **实施注意（钉死 — DB_PATH str/Path 兼容）**：4 个测试把 `routes.DB_PATH` monkeypatch 成 **`str`**（`test_api.py:10`、`test_campus_api.py:14`、`test_campus_intervention_api.py:10`、`test_campus_reproducibility_ab.py:92,152` 均 `setattr(routes, "DB_PATH", str(db_path))`）以重定向写入、隔离真实 `database/simulation.db`。`init_db()` 中建库目录的那行因此必须对 `str` 与 `Path` 都成立：
>
> - **首选（零改动）**：保持 `os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)` 不变——`os.path.dirname` 接受 path-like，`DB_PATH` 为 `Path`（默认）或 `str`（monkeypatch）都正确。
> - **等价替代**：`Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)`（`Path(...)` 包裹同样兼容）。
> - **禁止**：裸 `DB_PATH.parent`（`str` 无 `.parent` → 炸）；固定 `DATABASE_DIR`（忽略 monkeypatch、削弱隔离、可能写真实库）。
>
> `paths.py` 的 `DB_PATH` 保持 `Path`；`sqlite3.connect(DB_PATH)`（多处）接受 `str`/`Path`，无需改。无论选首选或替代，由 §6 门 7 守门测试锁定。

### 5.2 import 改写规则

| 现状 | 改写后 |
|------|--------|
| `from simulation.X import …` | `from canteen.simulation.X import …` |
| `from simulation import SimulationEngine` | `from canteen.simulation import SimulationEngine` |
| `from api.X import …` | `from canteen.api.X import …` |
| `from api import …`（包级非点形式，`app.py:11` `from api import api_bp, init_db`） | `from canteen.api import …` |
| `import api.routes as …`（含函数内缩进） | `import canteen.api.routes as …` |
| `from app import …`（5 处测试，**均函数内缩进**：`test_api.py:15`、`test_campus_api.py:24`、`test_campus_intervention_api.py:20`、`test_campus_reproducibility_ab.py:102,161`） | `from canteen.app import …` |
| 包内相对 `from .student import …` 等 | **不变** |
| 测试 `Path(__file__).resolve().parents[2]`（=repo 根，**全 9 处 / 8 文件**，含 `test_frontend_three_js_contract.py:2585` 行内用法，非仅顶部 `REPO_ROOT` 常量） | `parents[1]`；用 `rg "parents\[2\]"` 全扫替换 |
| 测试 `'frontend/static/...'` 字面量 | **不变**（保留 `frontend/`） |

### 5.3 `pyproject.toml`

要点（具体版本/字段实施时定稿）：

```toml
[build-system]
requires = ["setuptools>=64"]
build-backend = "setuptools.build_meta"

[project]
name = "canteen"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["flask>=3.0.0", "flask-cors>=4.0.0", "simpy>=4.1.1"]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"canteen.simulation.presets" = ["*.json"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 5.4 `conftest.py`（repo 根，新增）

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
```

作用：未 `pip install -e .` 时也能 `import canteen.*`，让 `pytest` 开箱即用。pytest 会**无条件先行收集 repo 根 `conftest.py`**（早于、且不受 `[tool.pytest.ini_options] testpaths = ["tests"]` 收集范围限制），故 `src/` 注入对 `tests/` 下所有用例都生效。原 `backend/tests/conftest.py` 的"注入 `backend/`"逻辑随之冗余 → 删除；`REPO_ROOT`/`VENDOR` 等锚点本就在各测试文件内（非 conftest），按 §5.2 改 `parents[2]→parents[1]` 即可。

### 5.5 运行与测试命令（Phase 2 写入文档）

- 安装：`./.venv/bin/pip install -e .`（或 `pip install -r requirements.txt`，后者内容为 `-e .`）。
- 起服：`./.venv/bin/python -m canteen`（`__main__.py` 固定 5001，保留旧体验）；或 `flask --app canteen.app run -p 5001`（**必须显式 `-p 5001`**，否则 Flask 默认 5000）。
- 测试：`./.venv/bin/python -m pytest tests -q`（root conftest 注入 `src/`，无需先安装）。

---

## 6. 验收门（Acceptance Gates）

迁移完成的客观判定（Phase 1 结束时全部满足）：

1. **裸 import 清零**（含 `app`）：
   ```bash
   rg -n "^\s*(from|import)\s+(api|simulation|app)\b" src tests
   ```
   必须**无输出**。要点：
   - `^\s*` 前缀确保抓到函数体内缩进的 import——5 处 `from app import create_app` 与 `import api.routes as routes` 都是缩进的。
   - 模块名必须含 `app`：`app.py` 迁移后这些测试须改成 `from canteen.app import …`，否则过不了本门；旧 `(api|simulation)` 正则会**漏掉** `from app import …`。`app\b` 的词边界不会误伤 `application` 等（`appl` 中 `app` 后无词边界）。
   - 只扫 `src`、`tests`，故 `docs/` 示例文本天然排除；改写后的 `from canteen.api/simulation/app …` 因前缀是 `canteen` 而不被命中。
   - 对应守门测试用 `re.compile(r"^\s*(from|import)\s+(api|simulation|app)\b", re.M)` 实现。
2. **路径中心化生效**：`from canteen.paths import REPO_ROOT, FRONTEND_ROOT, DB_PATH`，且 `REPO_ROOT` 指向仓库根、`FRONTEND_ROOT.is_dir()`、`DATABASE_DIR` 为 repo 根下 `database`。
3. **preset loader 冒烟**：
   ```bash
   ./.venv/bin/python -c "from canteen.simulation.presets.loader import load_single_canteen_preset; load_single_canteen_preset()"
   ```
   无异常。
4. **全套测试绿**：`./.venv/bin/python -m pytest tests -q` 全通过，用例总数不少于迁移前（迁移前基线：`PYTHONPATH=backend pytest backend/tests -q`）。
5. **起服**：`python -m canteen` 监听 5001 成功。
6. **浏览器冒烟**：访问 `http://127.0.0.1:5001/`，走 config→start→run→finish→统计/历史，控制台 **0 error**，3D canvas 非空。
7. **DB_PATH monkeypatch 兼容**：把 `canteen.api.routes.DB_PATH` 分别 monkeypatch 成 `tmp_path/'test.db'`（`Path`）与 `str(tmp_path/'test.db')`（`str`），两种 `init_db()` 都成功；且全程不写真实 `database/simulation.db`。

---

## 7. 分阶段执行

全程在分支 `restructure/standard-package`。

### Phase 0 · 守门测试先行（预飞，**不提交**）

- 新增 `tests/test_package_migration_guard.py`（暂写在当前 `backend/tests/`，随 Phase 1 一起移入 `tests/`），覆盖 §6 的门 1/2/3/7：
  - `test_no_bare_api_simulation_imports`（正则含 `^\s*`，扫 `src`、`tests`）；
  - `test_paths_module_points_to_repo_root`；
  - `test_preset_loader_importable`；
  - `test_init_db_accepts_str_and_path_db_path`：monkeypatch `canteen.api.routes.DB_PATH` 为 `Path` 与 `str` 两形态，`init_db()` 均成功且不触碰真实 `database/simulation.db`（对应 §6 门 7）。
- 本地运行，**确认全部 RED**（因 `canteen` 包此刻不存在），记录预期失败。
- **本阶段不 commit**——避免提交红测试违背"每个 commit 可跑、可回退"。

### Phase 1 · 建包（原子，绿后单次提交）

按依赖顺序执行，全部完成且 §6 验收门全绿后**一次性提交守门测试 + 实现**：

1. `git mv backend/app.py src/canteen/app.py`、`git mv backend/api src/canteen/api`、`git mv backend/simulation src/canteen/simulation`；新增 `src/canteen/__init__.py`、`__main__.py`、`paths.py`。
2. 新增 `pyproject.toml`、repo 根 `conftest.py`；`requirements.txt` 改 `-e .`。
3. 改写所有绝对 import（§5.2），含 `campus_routes.py:9`；相对 import 不动。
4. `git mv backend/tests tests`；改写测试绝对 import；用 `rg "parents\[2\]"` 把 **9 处** `parents[2]→parents[1]`（含 `test_frontend_three_js_contract.py:2585` 行内用法，非仅顶部 `REPO_ROOT` 常量）；删除 `tests/conftest.py` 原"注入 backend/"逻辑。
5. `app.py`、`api/routes.py` 改用 `canteen.paths`；删 `sys.path.insert`。`init_db()` 建库目录那行保持 `os.path.dirname(DB_PATH)`（已 str/Path 兼容）或换 `Path(DB_PATH).parent.mkdir(...)`，**禁止**裸 `DB_PATH.parent`（见 §5.1）。
6. `./.venv/bin/pip install -e .`。
7. 跑齐 §6 全部 7 道门；全绿后 `git add`（显式路径）+ commit。
8. 删空的 `backend/`（若残留）。

> **注意（worktree）**：`.worktrees/3d-canteen-digital-twin/` 内有一份平行 `backend/` 树（独立 git worktree），**不在本次迁移范围**。`git mv` / `rm backend` 只动主树，勿误碰；§6 守门只扫 `src tests`，不波及它。

### Phase 2 · 命令同步（绿，提交）

- 更新运行/验证命令文本：`README.md`、`AGENTS.md`、`agent.md`、`CLAUDE.md`（`AGENTS.md:7` 要求三份协作文件同步广义协作规则）。
- 新命令：`pip install -e .`、`python -m canteen` / `flask --app canteen.app run -p 5001`、`pytest tests -q`。
- **不改** `AGENTS.md:31-34` 对 `docs/superpowers/*` 与 `task_plan.md` 等的引用（它们未移动）。
- commit。

---

## 8. 风险与回退

| 风险 | 缓解 | 兜底 |
|------|------|------|
| 裸 import 残留 → `_session` 分裂 | 验收门 1（含缩进正则）+ 守门测试 | `git revert` Phase 1 提交 |
| repo-root 路径偏移到 `src/` | `paths.py` 中心化 + 验收门 2 | 同上 |
| presets 随包丢失 | package-data 声明 + 验收门 3 冒烟 | 同上 |
| Flask 端口回落 5000 | 文档与 `__main__.py` 显式 5001 | — |
| 未装包时测试失败 | repo 根 `conftest.py` 注入 `src/` | `PYTHONPATH=src` |

**整体回退**：Phase 1 是单个原子提交，`git revert` 即回到 `backend/` 布局；Phase 0 无提交、Phase 2 仅文档。

---

## 9. 后续（Spec B，不在本 Spec）

`docs/` 体系整理（phase3 PPT/报告归类、`reviews/`、worklog 文件）、`gen_docs.py`→`tools/`、`agent.md` 合并、前端大文件拆分（`state_adapter.js` / `main.js` / `analysis_charts.js` / `style.css`；`canteen_scene.js` 已按 `docs/superpowers/plans/2026-05-18-canteen-scene-split.md` 推进）。待本 Spec 结构稳定后单独立项。
