// 页面导航
const navLinks = document.querySelectorAll(".nav-link");
const pages = document.querySelectorAll(".page");

navLinks.forEach((link) => {
  link.addEventListener("click", function (e) {
    e.preventDefault();
    const targetPage = this.getAttribute("data-page");
    showPage(targetPage);
  });
});

function showPage(pageName) {
  pages.forEach((page) => {
    page.style.display = "none";
  });
  document.getElementById(`${pageName}-page`).style.display = "block";
}

// 参数配置表单
const configForm = document.getElementById("config-form");
const resetBtn = document.getElementById("reset-btn");

configForm.addEventListener("submit", async function (e) {
  e.preventDefault();

  const config = {
    window_count: parseInt(document.getElementById("window_count").value),
    seat_count: parseInt(document.getElementById("seat_count").value),
    avg_serve_time: parseFloat(document.getElementById("avg_serve_time").value),
    avg_eat_time: parseFloat(document.getElementById("avg_eat_time").value),
    arrival_rate: parseFloat(document.getElementById("arrival_rate").value),
    total_time: parseInt(document.getElementById("total_time").value),
  };

  try {
    const response = await fetch("http://localhost:5000/api/config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(config),
    });

    if (response.ok) {
      const data = await response.json();
      console.log("Configuration saved:", data);

      // 启动仿真
      const startResponse = await fetch(
        "http://localhost:5000/api/simulation/start",
        {
          method: "POST",
        },
      );

      if (startResponse.ok) {
        showPage("simulation");
        startSimulation();
      }
    }
  } catch (error) {
    console.error("Error:", error);
    alert("配置失败，请检查后端服务是否运行");
  }
});

resetBtn.addEventListener("click", function () {
  document.getElementById("window_count").value = 6;
  document.getElementById("seat_count").value = 200;
  document.getElementById("avg_serve_time").value = 30;
  document.getElementById("avg_eat_time").value = 15;
  document.getElementById("arrival_rate").value = 5;
  document.getElementById("total_time").value = 60;
});

// 仿真运行
let simulationInterval;
let speed = 1;

const playPauseBtn = document.getElementById("play-pause-btn");
const endBtn = document.getElementById("end-btn");
const speedSelect = document.getElementById("speed");

playPauseBtn.addEventListener("click", function () {
  if (this.textContent === "开始") {
    this.textContent = "暂停";
    startSimulation();
  } else {
    this.textContent = "开始";
    pauseSimulation();
  }
});

endBtn.addEventListener("click", function () {
  pauseSimulation();
  showPage("analysis");
  loadStatistics();
});

speedSelect.addEventListener("change", function () {
  speed = parseInt(this.value);
  if (playPauseBtn.textContent === "暂停") {
    pauseSimulation();
    startSimulation();
  }
});

function startSimulation() {
  clearInterval(simulationInterval);
  simulationInterval = setInterval(async function () {
    try {
      const response = await fetch("http://localhost:5000/api/simulation/step");
      if (response.ok) {
        const data = await response.json();
        updateSimulationUI(data);
        drawCanteen(data);

        if (data.is_ended) {
          clearInterval(simulationInterval);
          playPauseBtn.textContent = "开始";
          showPage("analysis");
          loadStatistics();
        }
      }
    } catch (error) {
      console.error("Error:", error);
    }
  }, 1000 / speed);
}

function pauseSimulation() {
  clearInterval(simulationInterval);
}

function updateSimulationUI(data) {
  const currentTime = Math.floor(data.current_time / 60);
  const minutes = Math.floor(currentTime / 60);
  const seconds = currentTime % 60;
  document.getElementById("current-time").textContent =
    `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  document.getElementById("total-arrived").textContent = data.total_arrived;
  document.getElementById("total-served").textContent = data.total_served;

  const emptySeats = data.seats.filter(
    (seat) => seat.status === "empty",
  ).length;
  document.getElementById("empty-seats").textContent = emptySeats;

  // 计算平均等待时间（这里简化处理，实际应该从后端获取）
  document.getElementById("avg-waiting-time").textContent = "0.0";
}

// Canvas绘制食堂布局
const canvas = document.getElementById("canteen-canvas");
const ctx = canvas.getContext("2d");

// 存储学生动画状态和历史数据
let studentAnimations = [];
let lastData = null;
let studentHistory = {}; // 存储学生的历史状态

function drawCanteen(data) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // 绘制窗口
  const windowWidth = 60;
  const windowHeight = 100;
  const windowSpacing = 20;
  const windowStartX =
    (canvas.width -
      (data.windows.length * (windowWidth + windowSpacing) - windowSpacing)) /
    2;
  const windowY = 50;

  data.windows.forEach((window, index) => {
    const x = windowStartX + index * (windowWidth + windowSpacing);

    // 绘制窗口
    ctx.fillStyle = "#4CAF50";
    ctx.fillRect(x, windowY, windowWidth, windowHeight);
    ctx.strokeStyle = "#333";
    ctx.strokeRect(x, windowY, windowWidth, windowHeight);

    // 绘制窗口编号
    ctx.fillStyle = "white";
    ctx.font = "16px Arial";
    ctx.textAlign = "center";
    ctx.fillText(
      `窗口 ${window.id + 1}`,
      x + windowWidth / 2,
      windowY + windowHeight / 2,
    );

    // 绘制排队
    const queueLength = window.queue_length;
    ctx.fillStyle = "#ff9800";
    for (let i = 0; i < queueLength; i++) {
      const queueX = x + windowWidth / 2 - 10;
      const queueY = windowY + windowHeight + 10 + i * 20;
      ctx.fillRect(queueX, queueY, 20, 20);
    }
  });

  // 绘制座位
  const seatSize = 30;
  const seatSpacing = 10;
  const seatsPerRow = 10;
  const totalSeats = data.seats.length;
  const totalRows = Math.ceil(totalSeats / seatsPerRow);

  // 计算居中位置
  const totalWidth = seatsPerRow * (seatSize + seatSpacing) - seatSpacing;
  const totalHeight = totalRows * (seatSize + seatSpacing) - seatSpacing;
  const seatStartX = (canvas.width - totalWidth) / 2;
  const seatStartY = 200;

  data.seats.forEach((seat, index) => {
    const row = Math.floor(index / seatsPerRow);
    const col = index % seatsPerRow;
    const x = seatStartX + col * (seatSize + seatSpacing);
    const y = seatStartY + row * (seatSize + seatSpacing);

    ctx.fillStyle = seat.status === "occupied" ? "#f44336" : "#4CAF50";
    ctx.fillRect(x, y, seatSize, seatSize);
    ctx.strokeStyle = "#333";
    ctx.strokeRect(x, y, seatSize, seatSize);
  });

  // 绘制等位队列
  const waitingQueueLength = data.waiting_queue_length;
  ctx.fillStyle = "#9c27b0";
  for (let i = 0; i < waitingQueueLength; i++) {
    const x = canvas.width - 50;
    const y = 200 + i * 20;
    ctx.fillRect(x, y, 20, 20);
  }

  // 处理动画
  updateAnimations(
    data,
    windowStartX,
    windowWidth,
    windowHeight,
    windowSpacing,
    windowY,
    seatStartX,
    seatStartY,
    seatSize,
    seatSpacing,
    seatsPerRow,
  );
  drawAnimations();

  // 保存当前数据
  lastData = data;
}

function updateAnimations(
  data,
  windowStartX,
  windowWidth,
  windowHeight,
  windowSpacing,
  windowY,
  seatStartX,
  seatStartY,
  seatSize,
  seatSpacing,
  seatsPerRow,
) {
  // 清除过期动画
  studentAnimations = studentAnimations.filter((anim) => anim.progress < 1);

  // 分析学生状态变化，生成真实动画
  if (data.students) {
    data.students.forEach((student) => {
      const studentId = student.id;
      const lastState = studentHistory[studentId];

      // 检查学生状态变化
      if (lastState && lastState.position !== student.position) {
        // 计算起始位置
        let startX, startY;

        // 特殊处理：从服务结束到就座的动画，确保从窗口出发
        if (
          lastState.position === "being_served" &&
          student.position === "seated"
        ) {
          const windowIndex = lastState.position_detail;
          startX =
            windowStartX +
            windowIndex * (windowWidth + windowSpacing) +
            windowWidth / 2;
          startY = windowY + windowHeight + 10;
        }
        // 特殊处理：从服务结束到等位的动画，确保从窗口出发
        else if (
          lastState.position === "being_served" &&
          student.position === "waiting_queue"
        ) {
          const windowIndex = lastState.position_detail;
          startX =
            windowStartX +
            windowIndex * (windowWidth + windowSpacing) +
            windowWidth / 2;
          startY = windowY + windowHeight + 10;
        }
        // 其他状态变化
        else if (lastState.position === "window_queue") {
          const windowIndex = lastState.position_detail;
          startX =
            windowStartX +
            windowIndex * (windowWidth + windowSpacing) +
            windowWidth / 2;
          startY = windowY + windowHeight + 10;
        } else if (lastState.position === "waiting_queue") {
          startX = canvas.width - 50;
          startY = 200 + lastState.position_detail * 20;
        } else if (lastState.position === "seated") {
          const row = Math.floor(lastState.position_detail / seatsPerRow);
          const col = lastState.position_detail % seatsPerRow;
          startX = seatStartX + col * (seatSize + seatSpacing) + seatSize / 2;
          startY = seatStartY + row * (seatSize + seatSpacing) + seatSize / 2;
        } else {
          // 默认起始位置
          startX = canvas.width / 2;
          startY = windowY + windowHeight;
        }

        // 计算目标位置
        let endX, endY;

        if (
          student.position === "window_queue" ||
          student.position === "being_served"
        ) {
          const windowIndex = student.position_detail;
          endX =
            windowStartX +
            windowIndex * (windowWidth + windowSpacing) +
            windowWidth / 2;
          endY = windowY + windowHeight + 10;
        } else if (student.position === "waiting_queue") {
          endX = canvas.width - 50;
          endY = 200 + student.position_detail * 20;
        } else if (student.position === "seated") {
          const row = Math.floor(student.position_detail / seatsPerRow);
          const col = student.position_detail % seatsPerRow;
          endX = seatStartX + col * (seatSize + seatSpacing) + seatSize / 2;
          endY = seatStartY + row * (seatSize + seatSpacing) + seatSize / 2;
        } else {
          // 离开系统
          endX = canvas.width / 2;
          endY = canvas.height - 50;
        }

        // 检查是否已经有该学生的动画
        const existingAnimation = studentAnimations.find(
          (anim) => anim.studentId === studentId,
        );
        if (!existingAnimation) {
          // 添加新动画
          studentAnimations.push({
            startX,
            startY,
            endX,
            endY,
            progress: 0,
            speed: 0.02, // 减慢速度
            studentId: studentId,
            studentInfo: student,
          });
        }
      } else if (!lastState) {
        // 新出现的学生，根据当前位置生成动画
        if (
          student.position === "seated" ||
          student.position === "waiting_queue"
        ) {
          // 新学生直接出现在座位或等位队列，从窗口位置开始动画
          const windowIndex = student.window_id || 0;
          const startX =
            windowStartX +
            windowIndex * (windowWidth + windowSpacing) +
            windowWidth / 2;
          const startY = windowY + windowHeight + 10;

          // 计算目标位置
          let endX, endY;

          if (student.position === "seated") {
            const row = Math.floor(student.position_detail / seatsPerRow);
            const col = student.position_detail % seatsPerRow;
            endX = seatStartX + col * (seatSize + seatSpacing) + seatSize / 2;
            endY = seatStartY + row * (seatSize + seatSpacing) + seatSize / 2;
          } else if (student.position === "waiting_queue") {
            endX = canvas.width - 50;
            endY = 200 + student.position_detail * 20;
          }

          // 添加新动画
          studentAnimations.push({
            startX,
            startY,
            endX,
            endY,
            progress: 0,
            speed: 0.02,
            studentId: studentId,
            studentInfo: student,
          });
        }
      }

      // 更新学生历史状态
      studentHistory[studentId] = {
        position: student.position,
        position_detail: student.position_detail,
        window_id: student.window_id,
        seat_id: student.seat_id,
      };
    });
  }

  // 更新动画进度
  studentAnimations.forEach((anim) => {
    anim.progress += anim.speed;
  });
}

function drawAnimations() {
  studentAnimations.forEach((anim) => {
    if (anim.progress < 1) {
      // 计算当前位置
      const x = anim.startX + (anim.endX - anim.startX) * anim.progress;
      const y = anim.startY + (anim.endY - anim.startY) * anim.progress;

      // 绘制移动轨迹
      ctx.strokeStyle = "rgba(255, 87, 34, 0.3)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(anim.startX, anim.startY);
      ctx.lineTo(x, y);
      ctx.stroke();

      // 绘制学生形象（简化版）
      ctx.save();
      ctx.translate(x, y);

      // 头部
      ctx.fillStyle = "#ff5722";
      ctx.beginPath();
      ctx.arc(0, -10, 8, 0, Math.PI * 2);
      ctx.fill();

      // 身体
      ctx.fillStyle = "#2196F3";
      ctx.fillRect(-6, 0, 12, 15);

      // 四肢（简单动画效果）
      const legOffset = Math.sin(Date.now() / 100) * 2;
      ctx.strokeStyle = "#2196F3";
      ctx.lineWidth = 2;

      // 左腿
      ctx.beginPath();
      ctx.moveTo(-3, 15);
      ctx.lineTo(-5, 20 + legOffset);
      ctx.stroke();

      // 右腿
      ctx.beginPath();
      ctx.moveTo(3, 15);
      ctx.lineTo(5, 20 - legOffset);
      ctx.stroke();

      // 左臂
      ctx.beginPath();
      ctx.moveTo(-6, 5);
      ctx.lineTo(-10, 10);
      ctx.stroke();

      // 右臂
      ctx.beginPath();
      ctx.moveTo(6, 5);
      ctx.lineTo(10, 10);
      ctx.stroke();

      ctx.restore();
    }
  });
}

// 添加动画循环
function animate() {
  if (lastData) {
    drawCanteen(lastData);
  }
  requestAnimationFrame(animate);
}

// 启动动画循环
animate();

// 数据分析
const restartBtn = document.getElementById("restart-btn");

restartBtn.addEventListener("click", function () {
  showPage("config");
});

async function loadStatistics() {
  try {
    const response = await fetch("http://localhost:5000/api/statistics");
    if (response.ok) {
      const stats = await response.json();
      updateStatisticsUI(stats);
      drawCharts(stats);
    }
  } catch (error) {
    console.error("Error:", error);
  }
}

function updateStatisticsUI(stats) {
  document.getElementById("stat-total-arrived").textContent =
    stats.total_arrived;
  document.getElementById("stat-avg-waiting").textContent =
    `${stats.avg_waiting_time.toFixed(1)}秒`;
  document.getElementById("stat-peak").textContent = stats.peak_queue_length;
  document.getElementById("stat-seat-utilization").textContent =
    `${stats.seat_utilization.toFixed(1)}%`;
}

function drawCharts(stats) {
  // 窗口服务人数图表
  const windowChart = echarts.init(document.getElementById("window-chart"));
  windowChart.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "shadow",
      },
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "3%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: stats.window_served.map((_, index) => `窗口 ${index + 1}`),
    },
    yAxis: {
      type: "value",
    },
    series: [
      {
        name: "服务人数",
        type: "bar",
        data: stats.window_served,
        itemStyle: {
          color: "#4CAF50",
        },
      },
    ],
  });

  // 排队人数变化图表（模拟数据）
  const queueChart = echarts.init(document.getElementById("queue-chart"));
  const queueData = [];
  for (let i = 0; i < 60; i++) {
    queueData.push(Math.floor(Math.random() * 50));
  }
  queueChart.setOption({
    tooltip: {
      trigger: "axis",
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "3%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: Array.from({ length: 60 }, (_, i) => `${i}分`),
    },
    yAxis: {
      type: "value",
    },
    series: [
      {
        name: "排队人数",
        type: "line",
        data: queueData,
        smooth: true,
        itemStyle: {
          color: "#ff9800",
        },
      },
    ],
  });

  // 座位利用率变化图表（模拟数据）
  const seatChart = echarts.init(document.getElementById("seat-chart"));
  const seatData = [];
  for (let i = 0; i < 60; i++) {
    seatData.push(Math.random() * 100);
  }
  seatChart.setOption({
    tooltip: {
      trigger: "axis",
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "3%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: Array.from({ length: 60 }, (_, i) => `${i}分`),
    },
    yAxis: {
      type: "value",
      max: 100,
    },
    series: [
      {
        name: "座位利用率",
        type: "area",
        data: seatData,
        itemStyle: {
          color: "rgba(76, 175, 80, 0.5)",
        },
        areaStyle: {
          color: "rgba(76, 175, 80, 0.3)",
        },
      },
    ],
  });
}

// 窗口大小变化时重新绘制图表
window.addEventListener("resize", function () {
  const windowChart = echarts.getInstanceByDom(
    document.getElementById("window-chart"),
  );
  const queueChart = echarts.getInstanceByDom(
    document.getElementById("queue-chart"),
  );
  const seatChart = echarts.getInstanceByDom(
    document.getElementById("seat-chart"),
  );

  if (windowChart) windowChart.resize();
  if (queueChart) queueChart.resize();
  if (seatChart) seatChart.resize();
});
