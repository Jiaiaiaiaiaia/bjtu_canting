"""Campus API statistics helper tests."""

from types import SimpleNamespace

from canteen.api.campus_stats_helpers import (
    aggregate_campus_timeline,
    build_campus_statistics,
    build_intervention_analysis,
)


def test_build_intervention_analysis_dedupes_events_and_reports_queue_drop():
    event = {
        "event_id": 1,
        "time": 60,
        "canteen_id": "minghu_xueyi",
        "floor_id": 2,
        "window_id": 4,
        "action": "open",
        "status": "applied",
        "changed": True,
        "metrics_before": {
            "campus_total_in_queue": 10,
            "open_window_count": 3,
        },
        "metrics_after": {
            "campus_total_in_queue": 5,
            "open_window_count": 4,
        },
    }
    history = [
        {
            "current_time": 30,
            "campus_totals": {"total_in_queue": 12},
            "interventions": [],
        },
        {
            "current_time": 60,
            "campus_totals": {"total_in_queue": 10},
            "interventions": [event],
        },
        {
            "current_time": 90,
            "campus_totals": {"total_in_queue": 4},
            "interventions": [dict(event)],
        },
    ]

    analysis = build_intervention_analysis(history)

    assert analysis["summary"] == "已记录 1 次窗口干预，1 次生效，0 次拒绝。"
    assert analysis["total_events"] == 1
    assert analysis["applied_count"] == 1
    assert analysis["rejected_count"] == 0
    assert analysis["events"][0]["avg_queue_before"] == 12
    assert analysis["events"][0]["avg_queue_after"] == 4
    assert analysis["events"][0]["avg_queue_delta"] == -8
    assert analysis["events"][0]["open_window_delta"] == 1
    assert analysis["events"][0]["verdict"] == "improved"
    assert (
        analysis["events"][0]["summary"]
        == "2F 窗4 增开窗口后开放窗口 +1，平均排队下降 8.0 人。"
    )


def test_build_intervention_analysis_summarizes_rejected_legacy_event():
    history = [
        {
            "current_time": 5,
            "campus_totals": {"total_in_queue": 3},
            "interventions": [
                {
                    "time": 5,
                    "canteen_id": "minghu_xueyi",
                    "floor_id": 1,
                    "window_id": 3,
                    "action": "close",
                    "status": "rejected",
                    "reason": "至少保留一个窗口",
                }
            ],
        }
    ]

    analysis = build_intervention_analysis(history)

    assert analysis["summary"] == "已记录 1 次窗口干预，0 次生效，1 次拒绝。"
    assert analysis["events"][0]["verdict"] == "rejected"
    assert analysis["events"][0]["summary"] == "1F 窗3 关窗被拒绝：至少保留一个窗口。"


def test_aggregate_campus_timeline_carries_last_value_per_minute():
    history = [
        {"current_time": 0, "campus_totals": {"total_in_queue": 2}},
        {"current_time": 130, "campus_totals": {"total_in_queue": 5}},
    ]

    assert aggregate_campus_timeline(history, "total_in_queue") == {
        "x": [0, 1, 2],
        "y": [2, 2, 5],
    }


def test_aggregate_campus_timeline_caps_reported_seat_utilization():
    history = [
        {"current_time": 0, "campus_totals": {"total_eating": 120}},
    ]

    assert aggregate_campus_timeline(history, "total_eating", normalize=100) == {
        "x": [0],
        "y": [99.0],
    }


def test_build_campus_statistics_preserves_coordinator_response_shape():
    windows = [
        SimpleNamespace(total_served=3),
        SimpleNamespace(total_served=4),
    ]
    canteen = SimpleNamespace(
        display_name="明湖",
        total_arrived=12,
        total_served=7,
        windows=windows,
        seats=[object(), object(), object(), object()],
        active_window_count=2,
    )
    stats = SimpleNamespace(
        avg_waiting_time=lambda: 6.5,
        avg_walk_time=lambda: 8.0,
        switch_rate=lambda: 0.5,
    )
    students = [
        SimpleNamespace(
            state="left",
            service_time=4,
            eat_time=5,
            walk_time=6,
            switch_count=1,
        ),
        SimpleNamespace(
            state="left",
            service_time=8,
            eat_time=15,
            walk_time=10,
            switch_count=0,
        ),
        SimpleNamespace(
            state="queueing",
            service_time=99,
            eat_time=99,
            walk_time=99,
            switch_count=99,
        ),
    ]
    coordinator = SimpleNamespace(
        env=SimpleNamespace(now=10),
        all_students=students,
        canteens={"minghu_xueyi": canteen},
        total_arrived=15,
        total_served=7,
        stats=stats,
    )
    coordinator.snapshot = lambda: {
        "current_time": 70,
        "campus_totals": {"total_in_queue": 5, "total_eating": 2},
        "canteens": {
            "minghu_xueyi": {
                "total_in_queue": 3,
                "total_eating": 2,
                "empty_seats": 2,
            }
        },
        "interventions": [],
    }
    history = [
        {"current_time": 0, "campus_totals": {"total_in_queue": 2, "total_eating": 1}},
        {"current_time": 70, "campus_totals": {"total_in_queue": 5, "total_eating": 2}},
    ]

    result = build_campus_statistics(coordinator, history, [])

    assert result["mode"] == "campus"
    assert result["total_arrived"] == 15
    assert result["total_served"] == 7
    assert result["total_switches"] == 100
    assert result["avg_waiting_time"] == 6.5
    assert result["avg_service_time"] == 6
    assert result["avg_eating_time"] == 10
    assert result["avg_walk_time"] == 8
    assert result["switch_rate"] == 0.5
    assert result["window_served"] == {"minghu_xueyi": [3, 4]}
    assert result["seat_utilization"] == 50
    assert result["peak_queue_length"] == 5
    assert result["queue_timeline"] == {"x": [0, 1], "y": [2, 5]}
    assert result["seat_util_timeline"] == {"x": [0, 1], "y": [25, 50]}
    assert result["intervention_analysis"]["summary"] == "暂无窗口干预事件。"
    assert result["canteen_statistics"]["minghu_xueyi"] == {
        "display_name": "明湖",
        "total_arrived": 12,
        "total_served": 7,
        "total_in_queue": 3,
        "total_eating": 2,
        "empty_seats": 2,
        "window_served": [3, 4],
        "seat_count": 4,
        "active_window_count": 2,
    }
