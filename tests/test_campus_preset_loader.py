from canteen.simulation.presets.loader import load_default_campus_preset


def test_default_campus_runtime_excludes_pending_xuehuo():
    preset = load_default_campus_preset()
    runtime_ids = [c["id"] for c in preset["config"]["canteens"]]

    assert runtime_ids == ["minghu_xueyi", "xuesi"]


def test_visible_canteen_metadata_keeps_xuehuo_as_pending_point():
    preset = load_default_campus_preset()
    visible_ids = [c["id"] for c in preset["visible_canteens"]]

    assert visible_ids == [
        "minghu_xueyi",
        "xuehuo",
        "xuesi",
    ]
    xuehuo = next(c for c in preset["visible_canteens"] if c["id"] == "xuehuo")
    assert xuehuo["runtime_included"] is False
    assert xuehuo["data_status"] == "missing"
    assert xuehuo["pending_data"] is True


def test_field_collected_canteens_keep_todo_but_are_labeled_review_pending():
    preset = load_default_campus_preset()
    by_id = {c["id"]: c for c in preset["visible_canteens"]}

    assert by_id["minghu_xueyi"]["_TODO_field_research_pending"] is True
    assert by_id["minghu_xueyi"]["data_status"] == "field_collected_pending_review"
    assert by_id["minghu_xueyi"]["runtime_included"] is True
    assert by_id["xuesi"]["_TODO_field_research_pending"] is True
    assert by_id["xuesi"]["data_status"] == "field_collected_pending_review"
    assert by_id["xuesi"]["runtime_included"] is True


def test_pending_canteens_are_not_routable():
    preset = load_default_campus_preset()

    assert preset["pending_canteens"] == ["xuehuo"]
    assert all(
        c["id"] != "xuehuo"
        for c in preset["config"]["canteens"]
    )


def test_default_preset_uses_demo_scale_runtime_with_source_scale_metadata():
    preset = load_default_campus_preset()
    campus = preset["config"]["campus"]

    assert campus["total_students"] == 180
    assert campus["peak_window_minutes"] == 20
    assert campus["simulation_seconds"] == 300
    assert preset["source_scale"]["total_students"] == 28000
    assert preset["source_scale"]["simulation_seconds"] == 5400
    assert preset["demo_runtime"] is True
