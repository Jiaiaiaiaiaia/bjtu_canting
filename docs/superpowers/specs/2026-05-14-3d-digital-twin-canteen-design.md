# 北京交通大学就餐仿真系统：3D 数字孪生主体验升级设计

**项目**：北京交通大学就餐仿真系统
**日期**：2026-05-14
**状态**：设计已确认，待实现计划拆分
**目标**：把现有食堂仿真从“2D 为主、3D 可选”升级为“3D 校园与食堂数字孪生主体验”，并支持运行中开关窗口影响后续排队。

---

## 1. 已确认的产品方向

本次升级采用 **Three.js 数字孪生主线**。系统仍保留 Flask + SimPy + plain JavaScript 的总体技术栈，不引入重型 GIS 主框架，也不把 3D 做成脱离后端的演示壳。

用户确认的关键选择如下：

- 地图真实度：采用“可信简化版”。校园沙盘保留北京交通大学主校区真实相对位置、明湖、主路、入口与食堂锚点，但不追求完整 GIS 级还原。
- 食堂内部：采用“较真实内部布局”。明湖学一按 3 层，学四按 2 层，使用现有 preset 中的楼层、窗口、座位数量生成 3D 内部。
- 窗口调节：采用“运行中开关/增加开放窗口数”。干预要进入后端仿真状态，不能只做前端视觉变化。
- 最终入口：校园 3D 地图优先。打开仿真运行页后，默认看到 3D 校园沙盘与人流。
- 视觉风格：深色数字孪生。强调发光动线、热力、KPI、监控式沙盘。
- 不降级原则：3D 是最终主体验，不再作为可选彩蛋。2D/SVG/Canvas 可以保留为兼容兜底或调试入口，但不作为主演示路径。

---

## 2. 技术路线调研结论

推荐路线是 **Three.js 主线 + 当前 Flask/SimPy 后端增强**。

Three.js 适合当前项目的原因是：现有仓库已经有 `frontend/static/js/three/scene3d.js`、本地 Three.js vendor 与 importmap 接入方式，继续增强的风险低；Three.js 对自定义校园沙盘、楼层堆叠、窗口/座位/学生点位、相机转场都足够灵活。

MapLibre GL JS 和 deck.gl 适合真实 GIS 地图、轨迹分析和地图底图叠加，但本项目已确认不是完整 GIS 还原路线。如果把 MapLibre/deck.gl 作为主框架，会引入一套新的地图生命周期和渲染模型，而食堂内部 3D 仍需回到 Three.js，整合成本高于收益。

独立 3D 原型路线适合快速展示视觉方向，但容易与真实 SimPy 状态脱节。本项目最终成果需要证明窗口干预影响真实排队，因此不应把原型壳作为主线。

参考资料：

- Three.js 官方 installation / import map / addons 文档：https://threejs.org/manual/en/installation.html
- MapLibre GL JS examples 与 3D buildings 示例：https://maplibre.org/maplibre-gl-js/docs/examples/
- deck.gl TripsLayer / PathLayer 文档：https://deck.gl/docs/api-reference/geo-layers/trips-layer
- 北京交通大学访客页 / 校园地图入口：https://www.bjtu.edu.cn/yhtd/fkjks/index.htm

---

## 3. 总体体验

用户打开仿真运行页后，默认进入深色 3D 校园沙盘。沙盘包含明湖、主路、校园入口、明湖学一、学四和学活待补点位。学生流从入口出发，根据后端 `CampusCoordinator` 的路由结果流向运行中的食堂。

点击明湖学一或学四后，进入该食堂 3D 内部。明湖学一按 3 层生成，学四按 2 层生成。每层展示窗口、座位、队列、人流与拥堵热力。用户可以切换楼层聚焦，也可以用剖面视角查看多层堆叠。

右侧或底部面板显示实时 KPI：校园平均等待、当前排队人数、完成数、座位利用率、拥堵楼层、最近干预事件。运行过程中，用户可以开关某一层的窗口。关闭窗口后，该窗口在 3D 中变暗或显示“关闭中”，后端不再把新学生分配给该窗口，后续队列与等待指标随仿真推进变化。

学活食堂继续显示为待补点位。它可以出现在校园沙盘中，但不可进入内部视图，不参与路由、排队、统计或最终 totals。

---

## 4. 系统架构

升级后的架构仍分为三层：

```text
Frontend 3D Layer
    scene3d.js / campus_scene.js / canteen_scene.js / intervention_ui.js
        |
Campus API Layer
    /api/campus/* + 新增窗口干预 API
        |
SimPy Kernel
    CampusCoordinator -> Canteen -> Window / Seat / Student
```

### 4.1 前端主体验层

前端将当前 `scene3d.js` 从“可选渲染模块”升级为 3D 主入口。建议拆分为：

- `scene3d.js`：Three.js 初始化、渲染循环、相机、场景切换、统一 `render(snapshot, state)` 入口。
- `campus_scene.js`：校园沙盘、明湖、道路、入口、食堂建筑、学活待补 marker、人流轨迹。
- `canteen_scene.js`：食堂内部楼层、窗口、座位、队列、学生点、楼层聚焦、剖面视角。
- `intervention_ui.js`：窗口开关控件、干预 API 调用、干预事件提示。
- 可选 `state_adapter.js`：把离散后端 snapshot 转换为稳定的 3D 渲染状态与插值目标。

页面布局调整为：左侧对象导航，中间全尺寸 3D 舞台，右侧指标/干预面板。原 2D SVG 校园图和 Canvas 食堂图不删除，但退到 fallback 或调试入口。

### 4.2 后端 API 层

Phase 2 单食堂接口保持不变：

- `/api/config`
- `/api/simulation/*`

校园联合仿真继续走：

- `/api/campus/config`
- `/api/campus/start`
- `/api/campus/step`
- `/api/campus/finish`
- `/api/campus/statistics`
- `/api/campus/history*`

新增窗口干预接口只作用于校园模式，不影响 Phase 2 单食堂兼容面。接口形态建议为：

```http
POST /api/campus/canteens/<canteen_id>/floors/<floor_id>/windows/<window_id>/toggle
Content-Type: application/json

{
  "open": false
}
```

返回值应包含：

- 更新后的目标食堂 snapshot；
- 更新后的 campus totals；
- 本次干预事件；
- 如果发生队列迁移，返回迁移人数与迁移目标概览。

### 4.3 SimPy 仿真层

`Window` 需要新增开放状态字段，例如：

- `is_open: bool`
- `closing: bool`

`Canteen.shortest_window()` 只在开放窗口里选择。`CampusCoordinator.snapshot()` 需要输出窗口开放状态、关闭中状态与干预事件，以便 3D 层准确展示。

---

## 5. 3D 场景设计

### 5.1 校园沙盘

校园沙盘使用真实锚点投影为简化 3D 坐标。第一版重点表现：

- 明湖水体；
- 主路与食堂间可读路径；
- 校园入口；
- 明湖学一、学四、学活待补点位；
- 从入口到食堂的学生流；
- 食堂建筑拥堵编码。

食堂建筑的颜色、发光强度或高度可以映射实时拥堵程度。例如总排队人数越高，建筑越红或发光越强。

### 5.2 食堂内部

食堂内部根据现有 preset 自动生成，而不是手写固定模型。

明湖学一：

- 3 层；
- 1F / 2F / 3F 的窗口数与座位数来自 `minghu_xueyi.json`；
- 支持楼层聚焦和多层剖面。

学四：

- 2 层；
- 窗口数与座位数来自 `xuesi.json`；
- 2F 面食等热点可以用 notes 显示为拥堵提示。

学活：

- 只在校园沙盘显示待补 marker；
- 不生成内部模型；
- 不参与运行仿真。

窗口、座位和学生的视觉编码：

- 开放窗口：正常发光；
- 关闭中窗口：变暗但保留服务中标记；
- 已关闭窗口：灰暗不可选；
- 空座：绿色或低亮度；
- 占用座：黄色；
- 排队学生：沿窗口前队列路径排列；
- 服务中学生：靠近窗口；
- 等座学生：进入座位等待区域；
- 就餐学生：落在座位矩阵。

---

## 6. 运行中窗口干预规则

窗口干预必须修改后端状态，不能只改变 3D 外观。

### 6.1 开窗

打开窗口后：

- `is_open` 设为 true；
- 下一次窗口选择时参与 `shortest_window()`；
- 前端窗口从暗色恢复为开放状态；
- snapshot/history 记录开窗事件。

### 6.2 关窗

关闭窗口后：

1. 如果窗口空闲且无队列，立即进入已关闭状态。
2. 如果窗口正在服务学生，服务不中断。窗口进入“关闭中”，当前服务结束后变为已关闭。
3. 如果窗口已有等待队列，等待学生需要重新分配到其他开放窗口。
4. 重新分配优先同层开放窗口；同层没有开放窗口时，转移到全食堂最短开放窗口。
5. 转移可以记录一个小的重排成本，例如 10-20 秒，用于避免关闭窗口无代价。
6. 每个运行中食堂至少保留 1 个开放窗口。后端拒绝关闭最后一个开放窗口，前端也应禁用该操作。

### 6.3 干预记录

每次干预写入 snapshot/history 中的 `interventions`：

- 时间；
- 食堂 id；
- 楼层 id；
- 窗口 id；
- 动作：open / close；
- 状态：applied / rejected / closing；
- 队列迁移人数；
- 拒绝原因（如关闭最后一个窗口）。

这些记录用于最后的分析页和演示脚本，证明窗口调节和仿真指标之间存在可追溯关系。

---

## 7. 数据流与状态同步

后端是唯一真实状态源。前端 3D 只做呈现、插值和交互，不自行生成仿真结果。

```text
SimPy events
    -> /api/campus/step snapshot
    -> StateAdapter
    -> Three.js continuous animation
    -> window intervention API
    -> updated backend state
    -> next snapshot
```

### 7.1 离散快照到连续动画

后端按固定 step 返回离散 snapshot。前端保存上一帧快照与当前快照，用 `requestAnimationFrame` 在两者之间插值。

校园在途学生使用 `in_transit.progress` 映射到路线位置。食堂内部学生按状态分组：

- queueing；
- serving；
- waiting seat；
- eating；
- completed。

渲染位置由状态和窗口/座位布局决定，不使用完全随机跳点。随机扰动只能用于避免点位重叠，不能改变统计含义。

### 7.2 KPI 与统计口径

右侧 KPI 优先使用后端返回的 totals，不从 Three.js 对象反推。最终分析页继续复用 `/api/campus/statistics`，避免出现 3D 页面和统计页面口径不一致。

热力图只是视觉编码，不反向改变仿真。

### 7.3 干预后的刷新

用户开关窗口后，前端调用干预 API。API 返回更新 snapshot 后，前端立即：

- 更新窗口视觉状态；
- 更新队列点位；
- 更新 KPI；
- 追加最近干预事件；
- 继续用下一次 `/api/campus/step` 推进仿真。

---

## 8. 测试与验收标准

验收目标不是“3D 看起来能动”，而是证明 3D 画面、后端状态、窗口干预和统计口径一致。

### 8.1 后端测试

必须保留全量后端回归：

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```

新增测试至少覆盖：

- 打开窗口后窗口参与后续选择；
- 关闭窗口后窗口不再接收新学生；
- 正在服务的窗口关闭时服务不中断；
- 关闭有等待队列的窗口后，等待学生迁移到开放窗口；
- 不能关闭某食堂最后一个开放窗口；
- 干预事件进入 snapshot/history；
- Phase 2 单食堂 API 响应形状不变。

### 8.2 前端契约测试

新增或更新前端契约测试，至少覆盖：

- 3D 主入口存在，默认校园运行页使用 3D 舞台；
- `scene3d.js` 暴露 `init/render/dispose`；
- 拆分模块能够读取同一 snapshot 字段；
- 学活待补 marker 可见但不可进入；
- 窗口开关控件会调用校园干预 API；
- WebGL 不可用时 fallback 可用，但不改变“3D 主体验”的产品定义。

JS 语法检查覆盖主文件和新增模块：

```bash
node --check frontend/static/js/main.js
node --input-type=module --check < frontend/static/js/three/scene3d.js
```

实现时应扩展到新增的 `campus_scene.js`、`canteen_scene.js`、`intervention_ui.js` 等模块。

### 8.3 浏览器验收

必须记录真实浏览器证据：

- 打开仿真页默认显示 3D 主屏；
- 校园 3D 沙盘可见；
- 学生流从入口流向食堂；
- 点击明湖学一进入 3D 内部；
- 点击学四进入 3D 内部；
- 楼层聚焦可用；
- 关闭窗口后窗口变暗，队列和 KPI 更新；
- console error 为 0；
- WebGL canvas 非空像素检查通过；
- 窄屏下核心控件不重叠。

建议证据保存到：

- `docs/phase3/screenshots/`
- `docs/phase3/browser_e2e_check.md`
- `docs/phase3/screenshots/three-result.json`

### 8.4 证明不是假动效

窗口干预验收必须包含同一仿真运行中的前后证据：

- 干预前 snapshot；
- 干预 API 响应；
- 干预后下一步 snapshot；
- history 中的 intervention 记录；
- 开放窗口数变化；
- 队列分布变化；
- 平均等待或总排队压力趋势变化。

如果这些证据缺失，不能宣称“窗口开关影响仿真”。

---

## 9. 实施分期建议

### Phase 1：3D 主屏重构

- 把运行页改为 3D 主屏布局；
- 拆分 `scene3d.js`；
- 校园沙盘成为默认运行视图；
- 保留 2D fallback。

### Phase 2：食堂内部 3D

- 用 preset 生成明湖学一 3 层内部；
- 用 preset 生成学四 2 层内部；
- 实现楼层聚焦、剖面视角、返回校园。

### Phase 3：窗口干预后端

- 给 `Window` 增加开放状态；
- 修改最短队列选择；
- 新增校园窗口干预 API；
- 处理关闭中、队列迁移、最后窗口保护；
- 写入干预事件。

### Phase 4：3D 干预 UI 与数据联动

- 右侧窗口开关面板；
- 调用干预 API；
- 3D 状态和 KPI 同步；
- 最近干预事件展示。

### Phase 5：证据与演示闭环

- 后端全量回归；
- 前端契约测试；
- 浏览器截图；
- canvas 非空像素检查；
- 干预前后 JSON 证据；
- 更新 3D 演示脚本。

---

## 10. 风险与边界

- 学活数据仍缺失，不能伪造为运行食堂。
- 3D 主体验不等于删除 2D；2D 可作为兜底，但不作为最终演示主线。
- 窗口干预必须先保证后端一致性，再做视觉增强。
- 不要把地图升级成完整 GIS 项目；第一版目标是可信简化校园沙盘。
- 不要让前端用随机动画伪造统计变化；统计变化必须来自后端 snapshot。
- 不要破坏 Phase 2 单食堂兼容接口。

---

## 11. 待实现计划输入

后续 implementation plan 应从以下任务开始拆分：

1. 增加后端窗口开放状态和干预测试；
2. 新增校园窗口干预 API；
3. 拆分 Three.js 前端模块；
4. 改造仿真运行页为 3D 主屏；
5. 实现校园沙盘默认入口；
6. 实现明湖学一 / 学四 3D 内部；
7. 实现窗口开关 UI 和干预事件展示；
8. 补齐浏览器 E2E 与证据文档。
