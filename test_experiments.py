"""
tests/test_experiments.py — Unit tests for Person #3's experiment runner.
Run with: pytest tests/test_experiments.py -v
"""

import pytest
from experiments import (
    sweep_size,
    sweep_assoc,
    compare_policies,
    heatmap_size_x_assoc,
    multilevel_stats,
)
from traces import make_trace


@pytest.fixture
def small_trace():
    """Small deterministic random trace."""
    return make_trace("random", n=500)


class TestSweepSize:

    def test_returns_correct_shape(self, small_trace):
        sizes = [4 * 1024, 8 * 1024, 16 * 1024]
        out_sizes, hr = sweep_size(small_trace, sizes,
                                   policies=["LRU"], assoc=4)
        assert out_sizes == sizes
        assert list(hr.keys()) == ["LRU"]
        assert len(hr["LRU"]) == len(sizes)

    def test_hit_rate_monotone(self, small_trace):
        """Bigger cache → higher (or equal) hit rate."""
        sizes = [4 * 1024, 16 * 1024, 64 * 1024]
        _, hr = sweep_size(small_trace, sizes,
                           policies=["LRU"], assoc=4)
        rates = hr["LRU"]
        assert rates[0] <= rates[1] <= rates[2]

    def test_all_three_policies(self, small_trace):
        sizes = [8 * 1024, 32 * 1024]
        _, hr = sweep_size(small_trace, sizes,
                           policies=["LRU", "Clock", "RRIP"], assoc=4)
        assert set(hr.keys()) == {"LRU", "Clock", "RRIP"}
        for p in ("LRU", "Clock", "RRIP"):
            assert all(0.0 <= r <= 1.0 for r in hr[p])


class TestSweepAssoc:

    def test_returns_correct_shape(self, small_trace):
        assocs = [1, 2, 4, 8]
        out_a, hr = sweep_assoc(small_trace, assocs, policies=["LRU"])
        assert out_a == assocs
        assert len(hr["LRU"]) == len(assocs)

    def test_higher_assoc_at_least_as_good(self, small_trace):
        """For LRU on a thrash-like trace, more assoc → ≥ hit rate."""
        trace = make_trace("thrash", n=2000)
        assocs = [1, 4, 16]
        _, hr = sweep_assoc(trace, assocs,
                            policies=["LRU"], size_bytes=8 * 1024)
        rates = hr["LRU"]
        # allow tiny slack
        assert rates[0] <= rates[1] + 0.01
        assert rates[1] <= rates[2] + 0.01


class TestComparePolicies:

    def test_returns_three_rates(self, small_trace):
        policies = ["LRU", "Clock", "RRIP"]
        out_p, rates = compare_policies(small_trace, policies=policies)
        assert out_p == policies
        assert len(rates) == 3
        assert all(0.0 <= r <= 1.0 for r in rates)


class TestHeatmap:

    def test_matrix_dimensions(self, small_trace):
        sizes  = [4 * 1024, 16 * 1024, 64 * 1024]
        assocs = [1, 2, 4]
        s, a, m = heatmap_size_x_assoc(small_trace, sizes, assocs)
        assert s == sizes
        assert a == assocs
        assert len(m) == len(sizes)
        for row in m:
            assert len(row) == len(assocs)
            assert all(0.0 <= v <= 1.0 for v in row)


class TestMultilevel:

    def test_contains_all_levels(self, small_trace):
        out = multilevel_stats(small_trace)
        for k in ("L1", "L2", "L3", "DRAM", "__summary__"):
            assert k in out

    def test_l1_accesses_match_trace_len(self, small_trace):
        out = multilevel_stats(small_trace)
        assert out["L1"]["accesses"] == len(small_trace)

    def test_l2_misses_equal_l3_accesses(self, small_trace):
        """Inclusive hierarchy invariant."""
        out = multilevel_stats(small_trace)
        # L2.accesses should equal L1.misses (cascading)
        assert out["L2"]["accesses"] == out["L1"]["misses"]
        assert out["L3"]["accesses"] == out["L2"]["misses"]
        # DRAM.accesses should equal L3.misses
        assert out["DRAM"]["accesses"] == out["L3"]["misses"]


class TestTraceGenerators:
    """Quick sanity tests for the trace stubs Person #3 wrote
    (they will be replaced/extended by Person #2)."""

    def test_all_traces_produce_lists_of_ints(self):
        from traces import list_traces
        for name in list_traces():
            t = make_trace(name, n=100)
            assert isinstance(t, list)
            assert len(t) > 0
            assert all(isinstance(a, int) for a in t)

    def test_sequential_is_strided(self):
        t = make_trace("sequential", n=10)
        # adjacent addresses should differ by a power of 2 (block size)
        diff = t[1] - t[0]
        assert diff > 0
        assert (diff & (diff - 1)) == 0


class TestThreeC:
    """Sanity tests for the 3C classifier stub."""

    def test_sequential_is_all_compulsory(self):
        from traces import classify_3c
        # Sequential trace with stride = block → every access is a new block
        addrs = [i * 64 for i in range(200)]
        r = classify_3c(addrs, size_bytes=32 * 1024,
                        associativity=4, block_size=64)
        assert r["compulsory"] == 200
        assert r["capacity"] == 0
        assert r["conflict"] == 0

    def test_repeated_access_not_a_miss(self):
        from traces import classify_3c
        # Access the same block 50 times → 1 compulsory, 0 capacity, 0 conflict
        addrs = [0x1000] * 50
        r = classify_3c(addrs, size_bytes=32 * 1024,
                        associativity=4, block_size=64)
        assert r["compulsory"] == 1
        assert r["capacity"] == 0
        assert r["conflict"] == 0

    def test_returns_correct_keys(self):
        from traces import classify_3c
        r = classify_3c([0, 64, 128], size_bytes=1024,
                        associativity=2, block_size=64)
        assert set(r.keys()) == {"compulsory", "capacity", "conflict"}
