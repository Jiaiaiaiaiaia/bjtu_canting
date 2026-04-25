# 北京交通大学就餐仿真系统

软件综合实训第 3 小组 —— 朱思思（后端）、宋嘉桐（前端）、贾文霞（配置与分析）

## 运行方式

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend
python app.py
```

浏览器访问 http://127.0.0.1:5001/（macOS 默认 5000 端口被 AirPlay 占用）

## 目录结构

```
Canteen/
├── backend/                       # 后端（Python + Flask）
│   ├── app.py                     # Flask 入口
│   ├── simulation/                # 仿真引擎模块
│   │   ├── __init__.py
│   │   ├── engine.py              # 仿真驱动（离散事件）
│   │   ├── queue_sim.py           # 排队仿真
│   │   └── dining_sim.py          # 就餐仿真
│   └── api/
│       └── routes.py              # REST API 路由
├── frontend/                      # 前端（HTML + ECharts + Canvas）
│   ├── templates/index.html
│   └── static/
│       ├── css/style.css
│       └── js/main.js
├── database/                      # SQLite 数据库（运行时生成）
└── requirements.txt
```

## 核心功能

- 参数化仿真配置（窗口数、座位数、到达率、打饭/就餐时长等）
- 基于泊松过程的学生到达模型 + 最短队列窗口分配策略
- 离散事件驱动仿真引擎
- Canvas 食堂布局与 ECharts 数据统计可视化
- SQLite 快照记录，可查历史
