# 集成阶段联调 bug 日志

## 范围

- 日期：2026-05-12
- 目标：执行 A.18 双模式端到端联调
- 范围：
  - 单食堂模式：`/api/config -> /api/simulation/start -> /api/simulation/step -> /api/simulation/finish -> /api/statistics -> /api/history*`
  - 校园模式：`/api/campus/config -> /api/campus/start -> /api/campus/step -> /api/campus/finish -> /api/campus/statistics -> /api/campus/history*`
  - 前端联调：使用真实 `campus/step` 返回值驱动 `campus.js / campus_map.js / floor_tabs.js`

## 环境与限制

- 本地 Flask：`http://127.0.0.1:5001`
- 后端全量测试：`PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q`
- 前端契约测试集合：
  `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_main_js_contract.py backend/tests/test_frontend_campus_js_contract.py backend/tests/test_frontend_campus_map_js_contract.py backend/tests/test_frontend_floor_tabs_js_contract.py backend/tests/test_frontend_a16_ui_contract.py -q`
- 限制：
  - 当前线程未授予 Computer Use 浏览器权限，无法直接做真实浏览器点击与 console 抓取。
  - 本轮以“本机 API 串行联调 + 真实 snapshot 驱动前端脚本 harness”替代最后一层人工点测。

## 联调结果

### 单食堂模式

- 串行 e2e 结果正常：
  - `config_id=29`
  - `start.mode=single`
  - 首次 `step.event_type=arrival`
  - `finish.total_arrived=307`
  - `finish.total_served=307`
  - `/api/statistics` 同步返回 `total_arrived=307`、`total_served=307`
  - `/api/history/configs` 中对应 `snapshot_count=921`
  - `/api/history?config_id=29` 返回 `921` 条快照，最后事件为 `eat_end`

### 校园模式

- 串行 e2e 结果正常：
  - `config_id=30`
  - `start.mode=campus`
  - `step.mode=campus`
  - `step.canteen_order=["minghu_xueyi","xuehuo","xuesi"]`
  - `finish.campus_totals.total_arrived=20`
  - `finish.campus_totals.total_served=20`
  - `/api/campus/statistics` 同步返回 `total_arrived=20`、`total_served=20`
  - `/api/campus/history/configs` 中对应 `snapshot_count=108`
  - `/api/campus/history?config_id=30` 返回 `108` 条快照，最后事件为 `finish`

### 前端三层视图联调

- 使用真实 `campus/step` snapshot 驱动前端脚本，结果正常：
  - 校园地图 marker 数：`3`
  - 食堂下拉选项：`minghu_xueyi / xuehuo / xuesi`
  - 默认下钻食堂：`minghu_xueyi`
  - 明湖楼层 Tab：`全楼层 / 1F / 2F`
  - 地图点击 `xuesi` 后：
    - `applyViewState()` 被调用
    - `state.view` 切到 `canteen`
    - `state.activeCanteenId=xuesi`
    - 楼层 Tab 为 `全楼层 / 1F / 2F`
  - 点击 `xuesi` 的 `2F` 后：
    - `state.activeFloorId=2`
    - 当前绘制窗口数：`2`
    - 当前绘制座位数：`70`

## 本轮 bug 记录

| 编号 | 现象 | 根因 | 处理 | 状态 |
|---|---|---|---|---|
| A.18-01 | 本轮未发现新的阻塞性代码 bug | - | 无需修复 | Closed |

## 结论

- 现有代码已通过本轮 A.18 主链联调。
- 单食堂模式与校园模式的后端闭环可跑通。
- 校园地图、食堂下钻、楼层 Tab 在真实 snapshot 驱动下可正常协作。
- 剩余缺口不是代码 bug，而是“未做真实浏览器点击/console 观察”的人工验证层。
