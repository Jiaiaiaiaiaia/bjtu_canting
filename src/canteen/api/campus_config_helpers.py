"""Pure config helpers for the campus-backed simulation API."""

REQUIRED_TOP_LEVEL = ("campus", "canteens", "router")
REQUIRED_CAMPUS_FIELDS = (
    "total_students", "lunch_alpha", "coverage", "peak_window_minutes",
    "simulation_seconds", "entrance_position", "walking_speed_mps",
)


def validate_campus_config(payload: dict) -> str | None:
    for field in REQUIRED_TOP_LEVEL:
        if field not in payload:
            return f"缺少参数：{field}"
    campus = payload["campus"]
    for field in REQUIRED_CAMPUS_FIELDS:
        if field not in campus:
            return f"缺少 campus 参数：{field}"
    if not isinstance(payload["canteens"], list) or not payload["canteens"]:
        return "canteens 必须是非空列表"
    try:
        if float(campus["total_students"]) <= 0:
            return "学生总数必须大于 0"
        if float(campus["lunch_alpha"]) <= 0:
            return "午餐比例必须大于 0"
        if float(campus["coverage"]) <= 0:
            return "覆盖率必须大于 0"
        if float(campus["peak_window_minutes"]) <= 0:
            return "高峰窗口必须大于 0"
        if float(campus["simulation_seconds"]) <= 0:
            return "仿真时长必须大于 0"
        if float(campus["walking_speed_mps"]) <= 0:
            return "步行速度必须大于 0"
    except (TypeError, ValueError):
        return "campus 参数类型错误"
    return None


def campus_config_summary(payload: dict) -> dict:
    canteens = payload["canteens"]
    total_windows = 0
    total_seats = 0
    serve_times = []
    eat_times = []
    for canteen in canteens:
        eat_times.append(float(canteen.get("avg_eat_time_minutes", 0) or 0))
        for floor in canteen.get("floors", []):
            windows = floor.get("windows", {})
            seats = floor.get("seats", {})
            active_count = int(windows.get("active_count", 0) or 0)
            total_windows += active_count
            total_seats += int(seats.get("count", 0) or 0)
            serve_time = windows.get(
                "avg_serve_time_seconds",
                canteen.get("avg_serve_time_seconds", 0),
            )
            serve_times.extend([float(serve_time or 0)] * active_count)

    campus = payload["campus"]
    arrival_rate = (
        float(campus["total_students"])
        * float(campus["lunch_alpha"])
        * float(campus["coverage"])
        / float(campus["peak_window_minutes"])
    )
    return {
        "window_count": max(1, total_windows),
        "seat_count": max(1, total_seats),
        "avg_serve_time": sum(serve_times) / len(serve_times) if serve_times else 30.0,
        "avg_eat_time": sum(eat_times) / len(eat_times) if eat_times else 15.0,
        "arrival_rate": arrival_rate,
        "total_time": max(1, int(float(campus["simulation_seconds"]) / 60)),
    }
