"""
tests/test_core.py — Unit tests for Person #1's core module.
Run with: pytest tests/test_core.py -v
"""

import pytest
from core import CacheHierarchy, CacheLevel, make_policy


# ---------------------------------------------------------------------------
# CacheLevel basic tests
# ---------------------------------------------------------------------------

class TestCacheLevel:

    def _make(self, size=1024, assoc=2, block=64, policy="LRU"):
        return CacheLevel("L1", size, assoc, block, policy)

    def test_cold_miss(self):
        c = self._make()
        hit = c.access(0x0000)
        assert hit is False
        assert c.stats.misses == 1
        assert c.stats.hits == 0

    def test_warm_hit(self):
        c = self._make()
        c.access(0x0000)   # cold miss
        hit = c.access(0x0000)  # warm hit
        assert hit is True
        assert c.stats.hits == 1

    def test_different_blocks(self):
        c = self._make()
        c.access(0x0000)
        c.access(0x0040)  # different block (64B apart)
        assert c.stats.misses == 2

    def test_flush_resets_stats(self):
        c = self._make()
        c.access(0x0000)
        c.flush()
        assert c.stats.accesses == 0
        hit = c.access(0x0000)
        assert hit is False  # cold miss again

    def test_direct_mapped_conflict(self):
        # 1-way, 1024B cache, 64B blocks → 16 sets
        # addresses 0 and 1024 map to the same set
        c = CacheLevel("L1", 1024, 1, 64, "LRU")
        c.access(0)       # miss, installs tag 0 in set 0
        c.access(1024)    # maps to same set → evicts tag 0
        hit = c.access(0) # should be miss again
        assert hit is False

    def test_set_associative_no_conflict(self):
        # 2-way, same addresses
        c = CacheLevel("L1", 1024, 2, 64, "LRU")
        c.access(0)
        c.access(1024)    # maps to same set, but 2nd way available
        hit = c.access(0) # should still be a hit
        assert hit is True

    def test_invalid_size_raises(self):
        with pytest.raises(ValueError):
            CacheLevel("L1", 1000, 1, 64)  # 1000 not power of 2

    def test_invalid_block_raises(self):
        with pytest.raises(ValueError):
            CacheLevel("L1", 1024, 1, 60)  # 60 not power of 2

    def test_hit_rate(self):
        c = self._make()
        for _ in range(3):
            c.access(0x0000)  # 1 miss + 2 hits
        assert c.stats.hit_rate == pytest.approx(2/3)


# ---------------------------------------------------------------------------
# Policy tests
# ---------------------------------------------------------------------------

class TestPolicies:

    def _level(self, policy, assoc=4, size=1024):
        return CacheLevel("T", size, assoc, 64, policy)

    def test_lru_evicts_lru(self):
        # 1-way cache → every miss evicts previous block
        c = CacheLevel("L1", 64, 1, 64, "LRU")
        c.access(0)
        c.access(64)   # evicts 0
        assert c.access(0) is False   # 0 was evicted

    def test_clock_basic(self):
        c = self._level("Clock", assoc=2, size=128)
        c.access(0)
        c.access(64)   # 2 ways filled
        c.access(128)  # must evict one of them
        # After eviction, exactly one of 0/64 is still present
        h0 = c.lookup(0)
        h64 = c.lookup(64)
        assert h0 or h64   # at least one survives

    def test_rrip_basic(self):
        c = self._level("RRIP", assoc=2, size=128)
        c.access(0)
        c.access(64)
        c.access(0)    # hit → rrpv = 0 (near)
        c.access(128)  # miss → should evict 64 (rrpv=2) not 0 (rrpv=0)
        assert c.lookup(0) is True
        assert c.lookup(64) is False

    def test_unknown_policy(self):
        with pytest.raises(ValueError):
            make_policy("FIFO", 4)


# ---------------------------------------------------------------------------
# CacheHierarchy tests
# ---------------------------------------------------------------------------

class TestCacheHierarchy:

    def _make(self):
        return CacheHierarchy(
            l1_size=1024, l1_assoc=2, l1_block=64, l1_policy="LRU",
            l2_size=4096, l2_assoc=4, l2_block=64, l2_policy="LRU",
            l3_size=16384, l3_assoc=8, l3_block=64, l3_policy="LRU",
        )

    def test_first_access_is_dram(self):
        h = self._make()
        r = h.access(0x1000)
        assert r.hit_level == "DRAM"

    def test_second_access_is_l1(self):
        h = self._make()
        h.access(0x1000)
        r = h.access(0x1000)
        assert r.hit_level == "L1"

    def test_summary_keys(self):
        h = self._make()
        h.access(0)
        s = h.summary()
        for key in ("total_accesses", "L1_hit_rate", "DRAM_accesses", "MPKI"):
            assert key in s

    def test_flush_all(self):
        h = self._make()
        h.access(0)
        h.flush_all()
        assert h.total_accesses == 0
        assert h.dram_accesses == 0
        r = h.access(0)
        assert r.hit_level == "DRAM"  # cold miss after flush

    def test_avg_latency_l1_only(self):
        h = self._make()
        h.access(0)       # DRAM miss → fills all levels
        h.access(0)       # L1 hit
        h.access(0)       # L1 hit
        # 1 DRAM + 2 L1 → avg = (200 + 4 + 4) / 3 ≈ 69.3
        assert h.average_latency < 200
        assert h.average_latency > 4

    def test_mpki(self):
        h = self._make()
        for addr in range(0, 10 * 64, 64):   # 10 cold misses
            h.access(addr)
        # All 10 are DRAM accesses → MPKI = 10/10 * 1000 = 1000
        assert h.mpki() == pytest.approx(1000.0)
