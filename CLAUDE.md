# Claude Instructions

## 基本要求

- 默认使用中文回答。
- 修改代码前，先阅读相关文件，理解现有实现后再动手。
- 优先复用项目已有模式，不要随意引入新的架构、库或写法。
- 不确定时先说明假设，不要编造不存在的 API、文件或配置。
- 本仓库是食堂/餐厅就餐仿真项目；`模块一`、`设计文化概论`、PPT 产物属于另一个课程项目，不要混入本项目状态判断。

## 项目概览

- 项目名称：北京交通大学就餐仿真系统 / Canteen Simulation
- 项目用途：模拟学生到达食堂、排队打饭、就座就餐、离场、统计分析与历史记录；集成阶段扩展为多食堂联合仿真。
- 主要技术栈：Python、Flask、SimPy、SQLite、原生 HTML/CSS/JavaScript、ECharts。
- 后端框架：Flask。
- 前端框架：无前端框架，使用原生 JavaScript 和模板 HTML。
- 数据库：SQLite。
- 包管理器：Python `pip` + `requirements.txt`；当前核心项目不使用 `pnpm`。

## 项目结构

- `src/canteen/`：后端源码（标准 Python 包，`pip install -e .`）。
- `src/canteen/api/`：Flask API、数据库初始化与迁移。
- `src/canteen/simulation/`：仿真核心，包括单食堂兼容门面、多食堂协调器、学生生命周期、路由、统计。
- `tests/`：pytest 测试。
- `frontend/templates/`：页面模板。
- `frontend/static/`：CSS 与前端 JavaScript。
- `database/`：本地 SQLite 运行数据，通常不提交数据库文件。
- `docs/`：设计文档、实施计划、阶段交付物草稿。
- `outputs/`：生成产物与渲染中间文件；其中设计文化 PPT 内容不属于本 Canteen 项目。
- `AGENTS.md`：Codex 项目上下文守卫，工作前优先阅读。
- `agent.md`：通用 agent 协作说明。
- `CLAUDE.md`：Claude/Claude Code 协作说明。

## 开发规范

- 保持与现有代码风格一致。
- 不要大面积重构，除非明确要求。
- 新增功能优先小步修改，避免一次性改太多文件。
- 删除代码前先确认没有被引用。
- 不要随意修改配置文件、锁文件、环境变量文件。
- 单食堂 Phase 2 接口是兼容基线，除非明确要求，不要破坏 `/api/config` 与 `/api/simulation/*` 的响应形状。
- 多食堂 / campus 功能应走独立 campus API 与数据文件，不要硬塞进旧单食堂接口。

## 代码风格

- 命名遵循项目现有习惯。
- import 顺序保持与现有文件一致。
- 错误处理、日志、参数校验参考已有实现。
- 复杂逻辑需要添加简短注释，但不要写废话注释。
- 后端优先写清楚数据流和不变量，尤其是仿真时间、学生状态、队列、座位资源、数据库快照。

## 测试与验证

- 修改后尽量运行相关测试。
- 如果不能运行测试，需要说明原因。
- 涉及接口、数据库、仿真时钟、学生状态机、路由决策、历史记录时，要特别检查边界情况。
- 修 bug 时优先补聚焦回归测试，再改生产代码。

## 常用命令

```bash
# 安装依赖
./.venv/bin/pip install -r requirements.txt

# 启动后端开发服务
./.venv/bin/python -m canteen

# 运行全部后端测试
./.venv/bin/python -m pytest tests -q

# 运行单个测试文件
./.venv/bin/python -m pytest tests/test_engine.py -q

# 查看当前工作区改动
git status --short
```
