# 总览「分解楼层卡片」重构设计(Phase B)

日期:2026-06-12
状态:已与用户对齐三项关键决策,待 spec review 与用户终审
前置:A 批次(渲染卫生:半透明 depthWrite/阴影盒穿插/相机深度精度/renderOrder 阶梯)已完成并验证(合同 113 / 全量 381 通过)

## 1. 背景与目标

总览模式当前同时渲染三层全部家具、摊位、半透明墙体与数百个彩色 avatar,视觉噪声压过信息;用户(课程演示场景)反馈"展示效果差"。

目标:**总览 = 演示门面**——3 秒读懂建筑结构、各层负载与人流方向;全部细节交给点击后的 focus 模式。focus 模式渲染不动。

## 2. 已确认决策(2026-06-12,用户选定)

| 决策点 | 选择 |
|---|---|
| 总览学生表现 | 单色发光点(状态色:排队琥珀 / 就餐青 / 移动白),focus 保持现有 avatar |
| 总览家具 | 全部隐藏(桌椅集群、摊位四件套、照片参考墙、天花管线) |
| 层间距 FLOOR_V | 104 → 132([state_adapter.js:20](../../../frontend/static/js/three/state_adapter.js)) |

## 3. 总览渲染规格

### 3.1 楼层卡片
- 楼板:总览不透明(`OVERVIEW_FLOOR_SLAB_OPACITY` 0.07 → 1.0),保留暖象牙双色交替与热力模式着色,`depthWrite`/`renderOrder` 走 A 批次既定规则(opacity≥0.98 → 写深度)。
- 楼层渐变:`OVERVIEW_FLOOR_GRADIENT_OPACITY` [1.0, 0.64, 0.38] → [1.0, 1.0, 1.0](卡片不再靠透明度做纵深,纵深由 Y 间距 + 既有 Z 梯度 [48, 12, -24] 承担);`_applyFloorGradientMaterial` 因 scale=1 自然短路,无需删改。
- 层间距:`FLOOR_V = 132`。学生 y、楼层 baseY、楼梯核高度(`topY + FLOOR_H + 6`)均由 baseY 推导,自动跟随;`OVERVIEW_CAMERA_Y_PADDING` 等相机常数允许在实施时按浏览器实测微调。

### 3.2 总览隐藏清单(focus 独占)
半透明后墙/侧墙、照片玻璃窗墙(`photo window glass pane` 及黑框)、天花管线、照片参考墙、桌椅集群(`_addPhotoTableClusters`)、服务摊位四件套(`_addServiceStall` 的柜台/玻璃/菜单牌/状态灯)、地贴装饰板(f1 蛇形引导/取餐道/主通道、hotpot zone、service aisle)。

### 3.3 总览保留清单
楼层边带(楼层轮廓识别)、楼梯/电梯核(结构锚点,兼容工作区进行中的「垂直核 overview-only」改动)、入口标记、楼板轮廓线。

### 3.4 窗口热力块
- 总览下每个窗口渲染为一个小型热力块(尺寸约 12×2.4×18,位置=窗口位),颜色复用 `heatColor(队列饱和度)`;关闭窗口呈灰色。
- 保留 `userData.kind='window'`,raycaster 钻取行为与现状一致。

### 3.5 学生光点
- 总览:`_studentAvatar` 分支为 `_studentLightDot`——单 mesh 发光点(emissive,直径 ~2.4),颜色按状态:`queueing` 琥珀、`seated/dining` 青、其余移动态白;沿用现有位置/朝向/插值数据,不改 state_adapter 学生输出。
- focus:现有 avatar 不动。

### 3.6 每层 KPI 标牌
- 每层卡片左缘一块 sprite 标牌:`{n}F · 在场 {count} · 排队 {queue}`,数据来自 `frame.floors`(state_adapter 已提供,零后端改动)。
- `userData = { kind: 'floor', floorId }`,点击标牌即进入该层 focus(复用现有 raycaster 楼层钻取)。
- renderOrder 使用 A 批次 `DEFAULT_LABEL_RENDER_ORDER` 阶梯。

## 4. 兼容性与不动清单

- **不动**:state_adapter 数据流(除 `FLOOR_V` 常数)、后端 API 与响应形状、focus 模式全部渲染、干预 UI、2D 回退、热力模式开关语义。
- 与工作区未提交的「垂直交通核 overview-only」改动方向一致、互不冲突。
- Phase 2 单食堂接口契约(`/api/config`、`/api/simulation/*`)零接触。

## 5. 合同测试变更清单(规格变更,随实现同批落地)

重写(token 锁从"半透明总览"改为"卡片总览"):
- `test_canteen_floor_surfaces_do_not_hide_lower_levels`(钉 0.07/不遮下层语义 → 改为卡片语义 + 上层可视由间距保证)
- `test_focused_canteen_floor_uses_stable_readable_light_surface`(0.07 常数 token 同步)
- `test_state_adapter_keeps_overview_floors_visibly_separated`(FLOOR_V/渐变数组 token 同步)

新增:
- 总览隐藏清单 token(墙体/玻璃/家具/摊位仅 focus 分支)
- 窗口热力块 token
- 学生光点 token(overview 分支 + 状态色)
- KPI 标牌 token(文案格式 + userData.kind='floor')
- `FLOOR_V = 132` token

不动:focus 相关全部合同、A 批次新加的 5 条合同。

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| 不透明上层卡片遮挡下层后部 | FLOOR_V 132 + Z 梯度;实施后浏览器实测默认俯角可视性,必要时微调相机 padding |
| FLOOR_V 改动牵连相机取景 | 相机常数(`OVERVIEW_CAMERA_Y_PADDING` 等)列为实施期可调项,以浏览器截图为准 |
| 总览→focus 过渡动画在新间距下的观感 | 过渡走既有 `_camTarget` 插值,实测确认;不改状态机 |
| 热力模式与卡片化叠加 | 卡片不透明反而提升热力可读性;合同保留热力 token |

## 7. 验证计划

1. TDD:合同测试先红后绿;全量回归(基线 381)。
2. node ESM 语法 + import 绑定守门测试(已有 `test_canteen_scene_import_bindings_resolve`)。
3. 浏览器:总览环绕截图(三层卡片分离、无闪烁、KPI 标牌可读)、点击标牌进 focus、focus 细节完整、热力模式切换。
4. 用户终审视觉效果。
