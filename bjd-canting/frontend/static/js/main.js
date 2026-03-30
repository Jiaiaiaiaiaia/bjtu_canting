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
  const seatSize = 25; // 减小座位大小，以便显示更多座位
  const seatSpacing = 8; // 减小座位间距
  const seatsPerRow = 12; // 增加每行座位数
  const totalSeats = data.seats.length;
  const totalRows = Math.ceil(totalSeats / seatsPerRow);

  // 计算居中位置
  const totalWidth = seatsPerRow * (seatSize + seatSpacing) - seatSpacing;
  const totalHeight = totalRows * (seatSize + seatSpacing) - seatSpacing;
  const seatStartX = (canvas.width - totalWidth) / 2;
  const seatStartY = 220; // 进一步提高座位起始位置，增加与窗口的间距

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

  // 分析学生状态变化，生成有规律的动画
  if (data.students) {
    // 按学生ID排序，确保处理顺序一致
    const sortedStudents = [...data.students].sort((a, b) => a.id - b.id);

    sortedStudents.forEach((student) => {
      const studentId = student.id;
      const lastState = studentHistory[studentId];

      // 检查学生状态变化
      if (lastState && lastState.position !== student.position) {
        // 只处理关键状态变化：从服务结束到就座或等位
        if (
          (lastState.position === "being_served" &&
            student.position === "seated") ||
          (lastState.position === "being_served" &&
            student.position === "waiting_queue")
        ) {
          // 计算起始位置（从窗口出发）
          const windowIndex = lastState.position_detail;
          const startX =
            windowStartX +
            windowIndex * (windowWidth + windowSpacing) +
            windowWidth / 2;
          const startY = windowY + windowHeight + 10;

          // 计算目标位置
          let endX, endY;

          if (student.position === "seated") {
            const row = Math.floor(student.position_detail / 12);
            const col = student.position_detail % 12;
            endX = seatStartX + col * (25 + 8) + 25 / 2;
            endY = 220 + row * (25 + 8) + 25 / 2;
          } else if (student.position === "waiting_queue") {
            endX = canvas.width - 50;
            endY = 200 + student.position_detail * 20;
          }

          // 检查是否已经有该学生的动画
          const existingAnimation = studentAnimations.find(
            (anim) => anim.studentId === studentId,
          );
          if (!existingAnimation) {
            // 添加新动画，速度统一
            studentAnimations.push({
              startX,
              startY,
              endX,
              endY,
              progress: 0,
              speed: 0.015, // 统一速度，使动画更有规律
              studentId: studentId,
              studentInfo: student,
            });
          }
        }
      }
      // 新出现的学生，只处理从窗口到座位的动画
      else if (!lastState && student.position === "seated") {
        // 从窗口位置开始动画
        const windowIndex = student.window_id || 0;
        const startX =
          windowStartX +
          windowIndex * (windowWidth + windowSpacing) +
          windowWidth / 2;
        const startY = windowY + windowHeight + 10;

        // 计算目标位置
        const row = Math.floor(student.position_detail / 12);
        const col = student.position_detail % 12;
        const endX = seatStartX + col * (25 + 8) + 25 / 2;
        const endY = 220 + row * (25 + 8) + 25 / 2;

        // 添加新动画
        studentAnimations.push({
          startX,
          startY,
          endX,
          endY,
          progress: 0,
          speed: 0.015,
          studentId: studentId,
          studentInfo: student,
        });
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

  // 限制同时进行的动画数量，避免混乱
  if (studentAnimations.length > 3) {
    // 保留进度最小的3个动画
    studentAnimations = studentAnimations
      .sort((a, b) => a.progress - b.progress)
      .slice(0, 3);
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
      ctx.strokeStyle = "rgba(255, 193, 7, 0.5)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(anim.startX, anim.startY);
      ctx.lineTo(x, y);
      ctx.stroke();

      // 绘制黄色方块
      ctx.fillStyle = "#ffc107";
      ctx.fillRect(x - 10, y - 10, 20, 20);
      ctx.strokeStyle = "#333";
      ctx.strokeRect(x - 10, y - 10, 20, 20);
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
