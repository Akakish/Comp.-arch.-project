"""
core/policy.py — Replacement policy implementations.
Supported: LRU, Clock, RRIP (Static RRIP = SRRIP).
Author: Person #1 (core)
"""

from __future__ import annotations
from collections import OrderedDict
from typing import List, Optional
from .block import CacheBlock


class ReplacementPolicy:
    """Abstract base for replacement policies."""

    name: str = "base"

    def on_hit(self, block: CacheBlock, way: int, ways: List[CacheBlock]) -> None:
        """Called when *block* is a cache hit."""

    def on_miss(self, ways: List[CacheBlock]) -> int:
        """Return the way index to evict on a miss."""
        raise NotImplementedError

    def on_insert(self, block: CacheBlock, way: int, ways: List[CacheBlock]) -> None:
        """Called right after a new block is inserted at *way*."""


# ---------------------------------------------------------------------------
# LRU
# ---------------------------------------------------------------------------

class LRUPolicy(ReplacementPolicy):
    """
    Least-Recently Used.
    Tracks access order with an OrderedDict keyed by way index.
    The *least* recently used way is at the front (first item).
    """

    name = "LRU"

    def __init__(self, associativity: int):
        # order: front = LRU, back = MRU
        self._order: OrderedDict[int, None] = OrderedDict(
            (i, None) for i in range(associativity)
        )

    def on_hit(self, block: CacheBlock, way: int, ways: List[CacheBlock]) -> None:
        # Move to MRU position
        self._order.move_to_end(way)

    def on_miss(self, ways: List[CacheBlock]) -> int:
        # Evict LRU (front of ordered dict)
        lru_way, _ = next(iter(self._order.items()))
        return lru_way

    def on_insert(self, block: CacheBlock, way: int, ways: List[CacheBlock]) -> None:
        # Place at MRU position
        self._order.move_to_end(way)


# ---------------------------------------------------------------------------
# Clock (second-chance)
# ---------------------------------------------------------------------------

class ClockPolicy(ReplacementPolicy):
    """
    Clock / Second-Chance approximation of LRU.
    Each block has a reference bit; the hand sweeps and clears bits.
    """

    name = "Clock"

    def __init__(self, associativity: int):
        self._hand: int = 0
        self._assoc: int = associativity

    def on_hit(self, block: CacheBlock, way: int, ways: List[CacheBlock]) -> None:
        block.ref_bit = True

    def on_miss(self, ways: List[CacheBlock]) -> int:
        # Sweep until we find a block with ref_bit == False
        while ways[self._hand].ref_bit:
            ways[self._hand].ref_bit = False
            self._hand = (self._hand + 1) % self._assoc
        victim = self._hand
        self._hand = (self._hand + 1) % self._assoc
        return victim

    def on_insert(self, block: CacheBlock, way: int, ways: List[CacheBlock]) -> None:
        block.ref_bit = True


# ---------------------------------------------------------------------------
# RRIP (Static Re-Reference Interval Prediction)
# ---------------------------------------------------------------------------

class RRIPPolicy(ReplacementPolicy):
    """
    Static RRIP (SRRIP) — Jaleel et al., ISCA 2010.
    RRPV (Re-Reference Prediction Value) is a 2-bit counter (0-3).
    Inserted with RRPV = 2 (distant re-reference).
    On hit: RRPV set to 0 (near re-reference).
    Evict: find RRPV == 3; if none, increment all and retry.
    """

    name = "RRIP"
    MAX_RRPV = 3

    def __init__(self, associativity: int):
        self._assoc = associativity

    def on_hit(self, block: CacheBlock, way: int, ways: List[CacheBlock]) -> None:
        block.rrpv = 0

    def on_miss(self, ways: List[CacheBlock]) -> int:
        while True:
            for i, b in enumerate(ways):
                if b.rrpv == self.MAX_RRPV:
                    return i
            # Increment all RRPV values
            for b in ways:
                b.rrpv = min(b.rrpv + 1, self.MAX_RRPV)

    def on_insert(self, block: CacheBlock, way: int, ways: List[CacheBlock]) -> None:
        ways[way].rrpv = self.MAX_RRPV - 1   # distant re-reference = 2


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

POLICIES = {
    "LRU":   LRUPolicy,
    "CLOCK": ClockPolicy,
    "RRIP":  RRIPPolicy,
}


def make_policy(name: str, associativity: int) -> ReplacementPolicy:
    """Return a policy instance by name string."""
    name = name.upper()
    if name not in POLICIES:
        raise ValueError(f"Unknown policy '{name}'. Choose from: {list(POLICIES)}")
    return POLICIES[name](associativity)
