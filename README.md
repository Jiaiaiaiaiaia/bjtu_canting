# 北京交通大学就餐仿真系统

软件综合实训第 3 小组 —— 朱思思（后端）、宋嘉桐（前端）、贾文霞（配置与分析）

## 运行方式

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=backend ./.venv/bin/python backend/app.py
```

浏览器访问 http://127.0.0.1:5001/（macOS 默认 5000 端口被 AirPlay 占用）

## 当前系统形态

- 单食堂模式仍是 Phase 2 兼容基线，继续使用 `/api/config` 与 `/api/simulation/*`。
- 校园联合模式走独立 `/api/campus/*`，后端由 SimPy `CampusCoordinator` 协调多食堂、学生路由、步行与统计。
- 默认校园预设是演示规模 runtime：明湖/学一与学四参与仿真；学活只作为待补点位显示，不参与路由、排队或统计。
- 前端默认提供 2D 校园地图 / 食堂楼层视图，并提供可选 Three.js 3D 视图；2D 仍作为 fallback。
- 浏览器 E2E 证据记录在 `docs/phase3/browser_e2e_check.md`，截图在 `docs/phase3/screenshots/`。

## 验证命令

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
node --check frontend/static/js/main.js
node --check frontend/static/js/campus.js
node --check frontend/static/js/campus_map.js
node --check frontend/static/js/floor_tabs.js
node --input-type=module --check < frontend/static/js/three/scene3d.js
```

## 目录结构

```
Canteen/
├── backend/                       # 后端（Python + Flask）
│   ├── app.py                     # Flask 入口
│   ├── simulation/                # 仿真引擎模块
│   │   ├── engine.py              # 单食堂兼容门面
│   │   ├── coordinator.py         # 校园联合 SimPy 协调器
│   │   ├── router.py              # 学生路由/切换
│   │   └── presets/               # 校园/食堂预设数据
│   └── api/                       # 单食堂与校园 API
├── frontend/                      # 前端（HTML + ECharts + Canvas + Three.js）
│   ├── templates/index.html
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── main.js
│           ├── campus.js
│           ├── campus_map.js
│           ├── floor_tabs.js
│           └── three/
├── database/                      # SQLite 数据库（运行时生成）
├── docs/phase3/                   # 集成阶段证据与演示脚本
└── requirements.txt
```

## 核心功能

- 参数化仿真配置（窗口数、座位数、到达率、打饭/就餐时长等）
- 基于泊松过程的学生到达模型 + 最短队列窗口分配策略
- 离散事件驱动仿真引擎
- Canvas 食堂布局与 ECharts 数据统计可视化
- SQLite 快照记录，可查历史
- 校园联合仿真：多食堂路由、步行中学生、食堂下钻、楼层 Tab
- 默认校园预设入口与待补数据提示
- 可选 Three.js 3D 沙盘视图
