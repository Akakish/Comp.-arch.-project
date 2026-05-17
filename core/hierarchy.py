"""
core/hierarchy.py — Full L1→L2→L3→DRAM cache hierarchy.
Author: Person #1 (core)

This module wires up the cache levels and exposes a single
`access(addr)` entry point.  It also tracks DRAM accesses and
returns a per-access result tuple for the trace / analysis layers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from .cache_level import CacheLevel, CacheStats
from .policy import make_policy


# Typical latencies in cycles (configurable)
LATENCY = {
    "L1":   4,
    "L2":  12,
    "L3":  40,
    "DRAM": 200,
}


@dataclass
class AccessResult:
    """Result of a single memory access through the hierarchy."""
    address: int
    hit_level: str           # "L1", "L2", "L3", or "DRAM"
    latency_cycles: int
    is_compulsory: bool = False   # filled by 3C classifier (trace.py)
    is_capacity:   bool = False
    is_conflict:   bool = False


class CacheHierarchy:
    """
    Three-level inclusive cache hierarchy.

    Usage
    -----
    >>> from core.hierarchy import CacheHierarchy
    >>> h = CacheHierarchy()           # default config
    >>> result = h.access(0xDEADBEEF)
    >>> print(result.hit_level, result.latency_cycles)

    Parameters can be customised per-level via keyword arguments:
        l1_size, l1_assoc, l1_block, l1_policy
        l2_size, l2_assoc, l2_block, l2_policy
        l3_size, l3_assoc, l3_block, l3_policy
    """

    def __init__(
        self,
        # L1
        l1_size:   int = 32 * 1024,
        l1_assoc:  int = 4,
        l1_block:  int = 64,
        l1_policy: str = "LRU",
        # L2
        l2_size:   int = 256 * 1024,
        l2_assoc:  int = 8,
        l2_block:  int = 64,
        l2_policy: str = "LRU",
        # L3
        l3_size:   int = 8 * 1024 * 1024,
        l3_assoc:  int = 16,
        l3_block:  int = 64,
        l3_policy: str = "LRU",
    ):
        # Build levels bottom-up so each level knows its successor
        self.l3 = CacheLevel("L3", l3_size, l3_assoc, l3_block, l3_policy, next_level=None)
        self.l2 = CacheLevel("L2", l2_size, l2_assoc, l2_block, l2_policy, next_level=self.l3)
        self.l1 = CacheLevel("L1", l1_size, l1_assoc, l1_block, l1_policy, next_level=self.l2)

        self.levels: List[CacheLevel] = [self.l1, self.l2, self.l3]
        self.dram_accesses: int = 0

    # ------------------------------------------------------------------
    # Main access interface
    # ------------------------------------------------------------------

    def access(self, addr: int) -> AccessResult:
        """
        Simulate one memory load through the hierarchy.

        The access cascades: L1 → (miss) → L2 → (miss) → L3 → (miss) → DRAM.
        Stats are updated inside each CacheLevel.access() call.
        """
        # L1 hit?
        if self._hit(self.l1, addr):
            return AccessResult(addr, "L1", LATENCY["L1"])

        # L2 hit?
        if self._hit(self.l2, addr):
            self._install(self.l1, addr)          # inclusive: bring into L1
            return AccessResult(addr, "L2", LATENCY["L2"])

        # L3 hit?
        if self._hit(self.l3, addr):
            self._install(self.l2, addr)          # fill L2
            self._install(self.l1, addr)          # fill L1
            return AccessResult(addr, "L3", LATENCY["L3"])

        # DRAM miss
        self.dram_accesses += 1
        self._install(self.l3, addr)
        self._install(self.l2, addr)
        self._install(self.l1, addr)
        return AccessResult(addr, "DRAM", LATENCY["DRAM"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hit(self, level: CacheLevel, addr: int) -> bool:
        """
        Check for a hit in *level* and update its stats.
        Does NOT trigger recursive next_level fetching —
        the hierarchy handles cascading explicitly above.
        """
        level.stats.accesses += 1
        tag, set_index, _ = level._parse_address(addr)
        ways = level._sets[set_index]
        pol = level._policies[set_index]

        for way_idx, block in enumerate(ways):
            if block is not None and block.tag == tag:
                level.stats.hits += 1
                pol.on_hit(block, way_idx, ways)
                return True

        level.stats.misses += 1
        return False

    def _install(self, level: CacheLevel, addr: int) -> None:
        """Install a block into *level* (called after a miss is resolved)."""
        tag, set_index, _ = level._parse_address(addr)
        ways = level._sets[set_index]
        pol = level._policies[set_index]

        # If already present (e.g. inclusive fill), skip
        if any(b is not None and b.tag == tag for b in ways):
            return

        free_way = level._find_free_way(ways)
        if free_way is None:
            evict_way = pol.on_miss(ways)
            level.stats.evictions += 1
            free_way = evict_way

        from .block import CacheBlock
        new_block = CacheBlock(tag=tag)
        ways[free_way] = new_block
        pol.on_insert(new_block, free_way, ways)

    # ------------------------------------------------------------------
    # Aggregate stats helpers
    # ------------------------------------------------------------------

    @property
    def total_accesses(self) -> int:
        return self.l1.stats.accesses

    @property
    def average_latency(self) -> float:
        """Weighted average memory-access latency across all accesses."""
        n = self.total_accesses
        if n == 0:
            return 0.0
        total_cycles = (
            self.l1.stats.hits * LATENCY["L1"]
            + self.l2.stats.hits * LATENCY["L2"]
            + self.l3.stats.hits * LATENCY["L3"]
            + self.dram_accesses * LATENCY["DRAM"]
        )
        return total_cycles / n

    def mpki(self) -> float:
        """Misses per kilo-instruction (using DRAM accesses as final misses)."""
        n = self.total_accesses
        return (self.dram_accesses / n * 1000) if n else 0.0

    def summary(self) -> dict:
        """Return a flat summary dict for printing / JSON export."""
        n = self.total_accesses
        return {
            "total_accesses": n,
            "L1_hits": self.l1.stats.hits,
            "L1_misses": self.l1.stats.misses,
            "L1_hit_rate": self.l1.stats.hit_rate,
            "L2_hits": self.l2.stats.hits,
            "L2_misses": self.l2.stats.misses,
            "L2_hit_rate": self.l2.stats.hit_rate,
            "L3_hits": self.l3.stats.hits,
            "L3_misses": self.l3.stats.misses,
            "L3_hit_rate": self.l3.stats.hit_rate,
            "DRAM_accesses": self.dram_accesses,
            "avg_latency_cycles": round(self.average_latency, 2),
            "MPKI": round(self.mpki(), 3),
        }

    def flush_all(self) -> None:
        """Reset all cache levels and DRAM counter."""
        for lvl in self.levels:
            lvl.flush()
        self.dram_accesses = 0

    def __repr__(self) -> str:
        return (
            f"CacheHierarchy(\n"
            f"  {self.l1}\n"
            f"  {self.l2}\n"
            f"  {self.l3}\n"
            f")"
        )
