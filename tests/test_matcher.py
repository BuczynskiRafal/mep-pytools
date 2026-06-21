from fast_connect import ConnectorDomain, ConnectorInfo, find_best_pair


def p(i, x, y, z, domain=ConnectorDomain.PIPING, size=0.5):
    return ConnectorInfo(i, x, y, z, domain, size)


def test_picks_closest_compatible_pair():
    a = [p(0, 0, 0, 0), p(1, 10, 0, 0)]
    b = [p(0, 11, 0, 0), p(1, 0.2, 0, 0)]

    result = find_best_pair(a, b)

    assert result is not None
    assert result[0].source_index == 0  # a[0]
    assert result[1].source_index == 1  # b[1] at distance 0.2


def test_rejects_different_domains():
    a = [p(0, 0, 0, 0, ConnectorDomain.PIPING)]
    b = [p(0, 0, 0, 0, ConnectorDomain.DUCTING)]

    assert find_best_pair(a, b) is None


def test_rejects_mismatched_pipe_size_beyond_tolerance():
    a = [p(0, 0, 0, 0, size=0.5)]
    b = [p(0, 0, 0, 0, size=0.9)]

    assert find_best_pair(a, b, size_tolerance=0.01) is None


def test_returns_none_when_no_connectors():
    assert find_best_pair([], [p(0, 0, 0, 0)]) is None
