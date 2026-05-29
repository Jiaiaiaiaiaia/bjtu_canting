# 北京交通大学就餐仿真系统

软件综合实训第 3 小组 —— 朱思思（后端）、宋嘉桐（前端）、贾文霞（配置与分析）

## 运行方式

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./.venv/bin/python -m canteen
```

浏览器访问 http://127.0.0.1:5001/（macOS 默认 5000 端口被 AirPlay 占用）

## 当前系统形态

- 当前主体验是 3D 单食堂就餐仿真 / digital twin，默认进入明湖食堂三层视图。
- Phase 2 兼容基线继续保留 `/api/config` 与 `/api/simulation/*`。
- `/api/campus/*` 作为当前 3D 单食堂演示的技术入口复用，前端叙事保持一个食堂。
- 2D 视图继续作为 fallback、调试和兼容界面保留。
- 浏览器 E2E 证据记录在 `docs/phase3/browser_e2e_check.md`，截图在 `docs/phase3/screenshots/`。

## 验证命令

```bash
./.venv/bin/python -m pytest tests -q
node --check frontend/static/js/main.js
node --check frontend/static/js/campus.js
node --check frontend/static/js/floor_tabs.js
node --input-type=module --check < frontend/static/js/three/scene3d.js
```

## 目录结构

```
Canteen/
├── pyproject.toml                 # 打包 + 依赖（pip install -e .）
├── src/canteen/                   # 后端 Python 包
│   ├── app.py                     # Flask 工厂（python -m canteen）
│   ├── paths.py                   # repo-root 路径单一真相源
│   ├── simulation/                # 仿真引擎模块
│   │   ├── engine.py              # 单食堂兼容门面
│   │   ├── coordinator.py         # SimPy 协调器（当前服务单食堂 3D 演示）
│   │   ├── router.py              # 学生楼层/窗口选择与切换
│   │   └── presets/               # 食堂预设数据
│   └── api/                       # 单食堂兼容 API 与 3D 演示 API
├── tests/                         # pytest 测试
├── frontend/                      # 前端（HTML + ECharts + Canvas + Three.js）
│   ├── templates/index.html
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── main.js
│           ├── campus.js
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
- 3D 单食堂视图：楼层切换、窗口状态、学生轨迹、桌椅布局、楼梯与多角度展示
- 2D fallback 视图与楼层 Tab
