"""Pure statistics helpers for the campus-backed simulation API."""

from canteen.simulation.stats import reported_seat_utilization_percent


def _intervention_event_key(event: dict) -> tuple:
    if event.get("event_id") is not None:
        return ("event_id", event["event_id"])
    return (
        "legacy",
        event.get("time"),
        event.get("canteen_id"),
        event.get("window_id"),
        event.get("action"),
        event.get("status"),
        event.get("reason"),
    )


def _deduped_intervention_events(history: list[dict]) -> list[dict]:
    seen = set()
    events = []
    for snap in history:
        for event in snap.get("interventions") or []:
            key = _intervention_event_key(event)
            if key in seen:
                continue
            seen.add(key)
            item = dict(event)
            item.setdefault("snapshot_time", snap.get("current_time"))
            events.append(item)
    events.sort(key=lambda e: (e.get("time", 0), e.get("event_id") or 0))
    return events


def _metric_number(metrics: dict, field: str):
    value = (metrics or {}).get(field)
    return value if isinstance(value, (int, float)) else None


def _average_queue(history: list[dict], start: float, end: float):
    values = [
        snap["campus_totals"].get("total_in_queue")
        for snap in history
        if start <= float(snap.get("current_time", 0)) <= end
        and isinstance(snap.get("campus_totals"), dict)
        and isinstance(snap["campus_totals"].get("total_in_queue"), (int, float))
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _format_queue_delta(delta) -> str:
    if delta is None or abs(delta) < 0.5:
        return "平均排队基本持平"
    if delta < 0:
        return f"平均排队下降 {abs(delta):.1f} 人"
    return f"平均排队上升 {delta:.1f} 人"


def build_intervention_analysis(history: list[dict]) -> dict:
    events = _deduped_intervention_events(history)
    analyzed = []
    for event in events:
        event_time = float(event.get("time") or event.get("snapshot_time") or 0)
        before_metrics = event.get("metrics_before") or {}
        after_metrics = event.get("metrics_after") or {}
        queue_before = _metric_number(before_metrics, "campus_total_in_queue")
        queue_after = _metric_number(after_metrics, "campus_total_in_queue")
        avg_before = _average_queue(history, max(0, event_time - 300), event_time - 0.001)
        avg_after = _average_queue(history, event_time + 0.001, event_time + 300)
        if avg_before is None:
            avg_before = queue_before
        if avg_after is None:
            avg_after = queue_after

        if avg_before is not None and avg_after is not None:
            avg_delta = round(avg_after - avg_before, 2)
        elif queue_before is not None and queue_after is not None:
            avg_delta = round(queue_after - queue_before, 2)
        else:
            avg_delta = None

        open_before = _metric_number(before_metrics, "open_window_count")
        open_after = _metric_number(after_metrics, "open_window_count")
        open_delta = (
            int(open_after - open_before)
            if open_before is not None and open_after is not None
            else 0
        )

        status = event.get("status") or "applied"
        if status == "rejected":
            verdict = "rejected"
        elif avg_delta is None or abs(avg_delta) < 0.5:
            verdict = "neutral"
        elif avg_delta < 0:
            verdict = "improved"
        else:
            verdict = "worse"

        action = event.get("action") or ""
        if action == "add":
            action_label = "添加窗口"
        elif action == "open":
            action_label = "增开窗口"
        else:
            action_label = "关窗"
        floor_id = event.get("floor_id")
        window_id = event.get("window_id")
        target = (
            f"{floor_id}F 窗{window_id}"
            if floor_id is not None and window_id is not None
            else f"窗{window_id}"
        )
        if status == "rejected":
            summary = f"{target} {action_label}被拒绝：{event.get('reason') or '规则限制'}。"
        else:
            change_text = (
                f"开放窗口 {open_delta:+d}"
                if open_delta else "开放窗口不变"
            )
            summary = f"{target} {action_label}后{change_text}，{_format_queue_delta(avg_delta)}。"

        analyzed.append({
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type", "window_toggle"),
            "time": event_time,
            "canteen_id": event.get("canteen_id"),
            "floor_id": floor_id,
            "window_id": window_id,
            "action": action,
            "status": status,
            "changed": event.get("changed"),
            "reason": event.get("reason"),
            "queue_before": queue_before,
            "queue_after": queue_after,
            "avg_queue_before": avg_before,
            "avg_queue_after": avg_after,
            "avg_queue_delta": avg_delta,
            "open_window_delta": open_delta,
            "verdict": verdict,
            "summary": summary,
        })

    applied_count = sum(1 for e in events if e.get("status") != "rejected")
    rejected_count = sum(1 for e in events if e.get("status") == "rejected")
    if events:
        summary = (
            f"已记录 {len(events)} 次窗口干预，"
            f"{applied_count} 次生效，{rejected_count} 次拒绝。"
        )
    else:
        summary = "暂无窗口干预事件。"
    return {
        "summary": summary,
        "total_events": len(events),
        "applied_count": applied_count,
        "rejected_count": rejected_count,
        "events": analyzed,
    }


def aggregate_campus_timeline(history: list[dict], field: str, normalize=None) -> dict:
    if not history:
        return {"x": [], "y": []}
    effective_time = max(s["current_time"] for s in history)
    total_minutes = max(1, int(effective_time // 60) + 1)
    buckets = [None] * total_minutes
    for snap in history:
        minute = min(total_minutes - 1, int(snap["current_time"] // 60))
        value = snap["campus_totals"].get(field, 0)
        if normalize:
            value = value / normalize * 100
            if field == "total_eating":
                value = reported_seat_utilization_percent(value)
        buckets[minute] = value
    last = 0
    xs, ys = [], []
    for i, value in enumerate(buckets):
        if value is None:
            value = last
        else:
            last = value
        xs.append(i)
        ys.append(round(value, 2))
    return {"x": xs, "y": ys}


def build_campus_statistics(
    coordinator,
    history: list[dict],
    analysis_history: list[dict],
) -> dict:
    snapshot = coordinator.snapshot()
    served = [s for s in coordinator.all_students if s.state == "left"]
    service_times = [s.service_time for s in served]
    eating_times = [s.eat_time for s in served]
    walk_times = [s.walk_time for s in served]

    total_seats = sum(len(c.seats) for c in coordinator.canteens.values())
    effective_time = max(1.0, coordinator.env.now)
    used_seat_time = sum(eating_times)
    seat_utilization = (
        used_seat_time / (total_seats * effective_time) * 100
        if total_seats > 0 else 0
    )
    seat_utilization = reported_seat_utilization_percent(seat_utilization)

    if not history:
        history = [{
            "current_time": snapshot["current_time"],
            "campus_totals": snapshot["campus_totals"],
        }]
    if not analysis_history:
        analysis_history = [{
            "current_time": snapshot["current_time"],
            "campus_totals": snapshot["campus_totals"],
            "interventions": snapshot.get("interventions", []),
        }]
    peak_queue_length = max(
        s["campus_totals"].get("total_in_queue", 0) for s in history
    )

    canteen_statistics = {}
    window_served = {}
    for cid, canteen in coordinator.canteens.items():
        canteen_snap = snapshot["canteens"][cid]
        served_by_window = [w.total_served for w in canteen.windows]
        window_served[cid] = served_by_window
        canteen_statistics[cid] = {
            "display_name": canteen.display_name,
            "total_arrived": canteen.total_arrived,
            "total_served": canteen.total_served,
            "total_in_queue": canteen_snap["total_in_queue"],
            "total_eating": canteen_snap["total_eating"],
            "empty_seats": canteen_snap["empty_seats"],
            "window_served": served_by_window,
            "seat_count": len(canteen.seats),
            "active_window_count": canteen.active_window_count,
        }

    return {
        "mode": "campus",
        "total_arrived": coordinator.total_arrived,
        "total_served": coordinator.total_served,
        "total_switches": sum(s.switch_count for s in coordinator.all_students),
        "avg_waiting_time": coordinator.stats.avg_waiting_time(),
        "avg_service_time": (
            sum(service_times) / len(service_times) if service_times else 0
        ),
        "avg_eating_time": (
            sum(eating_times) / len(eating_times) if eating_times else 0
        ),
        "avg_walk_time": (
            sum(walk_times) / len(walk_times)
            if walk_times else coordinator.stats.avg_walk_time()
        ),
        "switch_rate": coordinator.stats.switch_rate(),
        "window_served": window_served,
        "seat_utilization": seat_utilization,
        "peak_queue_length": peak_queue_length,
        "queue_timeline": aggregate_campus_timeline(history, "total_in_queue"),
        "seat_util_timeline": aggregate_campus_timeline(
            history, "total_eating", normalize=total_seats
        ),
        "canteen_statistics": canteen_statistics,
        "intervention_analysis": build_intervention_analysis(analysis_history),
    }
