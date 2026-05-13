from simulation.random_streams import build_random_streams


def test_streams_are_reproducible_for_same_master_seed():
    a = build_random_streams(1234)
    b = build_random_streams(1234)

    assert a.arrival.random() == b.arrival.random()
    assert a.routing.random() == b.routing.random()
    assert a.service.random() == b.service.random()
    assert a.eat.random() == b.eat.random()


def test_streams_do_not_share_state_with_each_other():
    untouched = build_random_streams(1234)
    consumed = build_random_streams(1234)

    consumed.arrival.random()
    consumed.arrival.random()

    assert consumed.service.random() == untouched.service.random()
    assert consumed.eat.random() == untouched.eat.random()
