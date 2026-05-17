"""
core/cache_level.py — A single configurable cache level.
Author: Person #1 (core)

Address breakdown (byte-addressable):
    [ tag | set_index | block_offset ]
    block_offset = log2(block_size) bits
    set_index    = log2(num_sets)   bits
    tag          = remaining high bits
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Optional
from .block import CacheBlock
from .policy import ReplacementPolicy, make_policy


@dataclass
class CacheStats:
    """Counters collected during simulation."""
    accesses: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    dirty_evictions: int = 0   # reserved for write-back extension

    @property
    def hit_rate(self) -> float:
        return self.hits / self.accesses if self.accesses else 0.0

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate

    def __repr__(self) -> str:
        return (
            f"CacheStats(accesses={self.accesses}, hits={self.hits}, "
            f"misses={self.misses}, hit_rate={self.hit_rate:.2%})"
        )


class CacheLevel:
    """
    One level of the cache hierarchy.

    Parameters
    ----------
    name        : human label, e.g. "L1", "L2", "L3"
    size_bytes  : total cache capacity in bytes
    associativity: number of ways (1 = direct-mapped)
    block_size  : cache line size in bytes (must be power-of-2)
    policy      : replacement policy name ("LRU", "Clock", "RRIP")
    next_level  : next CacheLevel (or None for main memory)
    """

    def __init__(
        self,
        name: str,
        size_bytes: int,
        associativity: int,
        block_size: int,
        policy: str = "LRU",
        next_level: Optional["CacheLevel"] = None,
    ):
        if size_bytes <= 0 or (size_bytes & (size_bytes - 1)) != 0:
            raise ValueError(f"size_bytes must be a positive power of 2, got {size_bytes}")
        if block_size <= 0 or (block_size & (block_size - 1)) != 0:
            raise ValueError(f"block_size must be a positive power of 2, got {block_size}")
        if associativity <= 0:
            raise ValueError(f"associativity must be >= 1, got {associativity}")

        self.name = name
        self.size_bytes = size_bytes
        self.associativity = associativity
        self.block_size = block_size
        self.next_level = next_level

        # Derived geometry
        self.num_sets: int = size_bytes // (associativity * block_size)
        if self.num_sets < 1:
            self.num_sets = 1  # degenerate but don't crash

        self._offset_bits: int = int(math.log2(block_size))
        self._index_bits: int = int(math.log2(self.num_sets)) if self.num_sets > 1 else 0

        # Storage: list of sets, each set is a list of ways (CacheBlock | None)
        self._sets: List[List[Optional[CacheBlock]]] = [
            [None] * associativity for _ in range(self.num_sets)
        ]

        # One replacement policy instance per set
        self._policies: List[ReplacementPolicy] = [
            make_policy(policy, associativity) for _ in range(self.num_sets)
        ]

        self.stats = CacheStats()

    # ------------------------------------------------------------------
    # Address helpers
    # ------------------------------------------------------------------

    def _parse_address(self, addr: int):
        """Return (tag, set_index, block_offset) for a byte address."""
        block_offset = addr & (self.block_size - 1)
        set_index = (addr >> self._offset_bits) & (self.num_sets - 1)
        tag = addr >> (self._offset_bits + self._index_bits)
        return tag, set_index, block_offset

    # ------------------------------------------------------------------
    # Core access
    # ------------------------------------------------------------------

    def access(self, addr: int) -> bool:
        """
        Simulate a memory access (load).
        Returns True on hit, False on miss.
        On miss, fetches from next_level recursively.
        """
        self.stats.accesses += 1
        tag, set_index, _ = self._parse_address(addr)
        ways = self._sets[set_index]
        pol = self._policies[set_index]

        # --- Hit path ---
        for way_idx, block in enumerate(ways):
            if block is not None and block.tag == tag:
                self.stats.hits += 1
                pol.on_hit(block, way_idx, ways)
                return True

        # --- Miss path ---
        self.stats.misses += 1

        # Fetch from next level (or memory)
        if self.next_level is not None:
            self.next_level.access(addr)

        # Find a free way or evict
        free_way = self._find_free_way(ways)
        if free_way is None:
            evict_way = pol.on_miss(ways)
            self.stats.evictions += 1
            if ways[evict_way] and ways[evict_way].dirty:
                self.stats.dirty_evictions += 1
            free_way = evict_way

        # Install new block
        new_block = CacheBlock(tag=tag)
        ways[free_way] = new_block
        pol.on_insert(new_block, free_way, ways)
        return False

    def _find_free_way(self, ways: List[Optional[CacheBlock]]) -> Optional[int]:
        """Return index of first empty (None) way, or None if all occupied."""
        for i, b in enumerate(ways):
            if b is None:
                return i
        return None

    # ------------------------------------------------------------------
    # Lookup (without side effects — for 3C analysis)
    # ------------------------------------------------------------------

    def lookup(self, addr: int) -> bool:
        """Read-only hit check. Does NOT update stats or policy state."""
        tag, set_index, _ = self._parse_address(addr)
        return any(
            b is not None and b.tag == tag
            for b in self._sets[set_index]
        )

    # ------------------------------------------------------------------
    # Invalidation / flush helpers
    # ------------------------------------------------------------------

    def invalidate(self, addr: int) -> bool:
        """Remove a specific block from this level. Returns True if it was present."""
        tag, set_index, _ = self._parse_address(addr)
        ways = self._sets[set_index]
        for i, b in enumerate(ways):
            if b is not None and b.tag == tag:
                ways[i] = None
                return True
        return False

    def flush(self) -> None:
        """Invalidate all blocks and reset stats."""
        for s in self._sets:
            for i in range(len(s)):
                s[i] = None
        self.stats = CacheStats()
        # Re-create policy state
        pol_name = self._policies[0].name
        self._policies = [
            make_policy(pol_name, self.associativity) for _ in range(self.num_sets)
        ]

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """Return configuration as a plain dict (useful for README / reports)."""
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "associativity": self.associativity,
            "block_size": self.block_size,
            "num_sets": self.num_sets,
            "policy": self._policies[0].name,
        }

    def __repr__(self) -> str:
        kb = self.size_bytes // 1024
        return (
            f"CacheLevel({self.name}, {kb}KB, "
            f"{self.associativity}-way, {self.block_size}B blocks, "
            f"policy={self._policies[0].name}, sets={self.num_sets})"
        )
