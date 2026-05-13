# Demo Script

## 1. Single-Canteen Baseline

进入“参数配置”，保留单食堂模式或调整窗口、座位、到达率，点击“开始仿真”。在“仿真运行”页展示窗口队列、座位占用、学生流动圆点，然后点击“结束仿真”进入“数据分析”。这里说明 Phase 2 单食堂接口仍保持兼容，历史记录也能继续查看。

## 2. Campus Joint Simulation

回到“参数配置”，切换“校园联合模式”，选择“北交大午餐高峰预设”。说明默认演示使用 demo-scale runtime：明湖/学一和学四参与仿真，学活仍是待补数据，只显示为 pending 点位，不参与路由、队列和统计，避免把占位容量当成真实数据。

## 3. 2D / 3D Visualization

启动校园联合仿真后，先展示 2D 校园地图：三个 marker 可见，其中学活是半透明待补点位；点击学四进入食堂详情，展示楼层 Tab 与窗口/座位状态。然后切换到 3D，展示 Three.js 沙盘中的校园建筑、在途学生与食堂下钻；再切回 2D，证明 fallback 可用。

## 4. Evidence

展示 `docs/phase3/browser_e2e_check.md`：console error 为 0；单食堂和校园模式结束后 `total_arrived == total_served`；截图文件在 `docs/phase3/screenshots/`；3D canvas 像素非空并可切回 2D。
