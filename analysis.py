"""
traces/analysis.py — 3C miss classification.

NOTE for Person #2:
    Это рабочая заглушка с **точно той сигнатурой**, которую
    ожидает viz/demo.py и main.py:

        classify_3c(addrs, size_bytes, associativity, block_size) -> dict

    Внутри написана корректная (хоть и базовая) классификация
    Compulsory / Capacity / Conflict по классическому методу
    Hill–Smith:
        compulsory  = первый доступ к блоку
        capacity    = miss, который остался бы miss и в fully-associative
                      кэше того же размера
        conflict    = остальные miss-ы (т.е. fix-able большей ассоциативностью)

    Можешь либо оставить эту реализацию (она правильная),
    либо заменить более продвинутой версией — главное, сохрани
    сигнатуру и ключи возврата.
"""

from __future__ import annotations
import math
from collections import OrderedDict
from typing import List, Dict


# ─── helpers ─────────────────────────────────────────────────────────────

def _block_of(addr: int, block_size: int) -> int:
    return addr // block_size


# ─── tiny LRU fully-associative cache (just for the capacity oracle) ─────

class _FullyAssocLRU:
    """A fully-associative LRU of `nblocks` blocks (block-granularity only)."""

    def __init__(self, nblocks: int):
        self.nblocks = max(1, nblocks)
        self._od: "OrderedDict[int, None]" = OrderedDict()

    def access(self, block_id: int) -> bool:
        """Return True on hit, False on miss; updates LRU order."""
        if block_id in self._od:
            self._od.move_to_end(block_id)
            return True
        # miss
        self._od[block_id] = None
        if len(self._od) > self.nblocks:
            self._od.popitem(last=False)
        return False


# ─── tiny set-associative LRU (for the "actual" pass) ────────────────────

class _SetAssocLRU:
    """Set-associative LRU with the exact same geometry as `core.CacheLevel`."""

    def __init__(self, size_bytes: int, associativity: int, block_size: int):
        # tolerate degenerate configs (round up to 1 set)
        num_sets = max(1, size_bytes // (associativity * block_size))
        self.num_sets = num_sets
        self.assoc    = associativity
        self.block    = block_size
        self._sets: List["OrderedDict[int, None]"] = [
            OrderedDict() for _ in range(num_sets)
        ]

    def _parse(self, block_id: int):
        set_idx = block_id % self.num_sets
        tag     = block_id // self.num_sets
        return set_idx, tag

    def access(self, block_id: int) -> bool:
        s, tag = self._parse(block_id)
        bucket = self._sets[s]
        if tag in bucket:
            bucket.move_to_end(tag)
            return True
        bucket[tag] = None
        if len(bucket) > self.assoc:
            bucket.popitem(last=False)
        return False


# ─── public API ──────────────────────────────────────────────────────────

def classify_3c(
    addrs: List[int],
    size_bytes: int,
    associativity: int,
    block_size: int,
) -> Dict[str, int]:
    """
    Classify every miss in `addrs` as Compulsory, Capacity, or Conflict.

    Method (Hill–Smith 3C model):
        1.  pass through the actual set-associative LRU cache → record misses
        2.  pass through a fully-associative LRU cache of the same total size
            (same #blocks) → its misses are Compulsory + Capacity
        3.  the very first access to any block is Compulsory; the remaining
            FA-misses are Capacity; everything that is a miss in (1) but a hit
            in (2) is a Conflict miss.

    Parameters
    ----------
    addrs           : list of byte addresses
    size_bytes      : total cache size in bytes
    associativity   : number of ways
    block_size      : line size in bytes

    Returns
    -------
    {"compulsory": int, "capacity": int, "conflict": int}
    """
    if not addrs:
        return {"compulsory": 0, "capacity": 0, "conflict": 0}

    nblocks = max(1, size_bytes // block_size)

    actual = _SetAssocLRU(size_bytes, associativity, block_size)
    fa     = _FullyAssocLRU(nblocks)

    seen_blocks: set[int] = set()
    compulsory = 0
    capacity   = 0
    conflict   = 0

    for a in addrs:
        b = _block_of(a, block_size)

        actual_hit = actual.access(b)
        fa_hit     = fa.access(b)

        if b not in seen_blocks:
            seen_blocks.add(b)
            compulsory += 1
            # compulsory is also a miss in both caches; we don't double-count.
            continue

        # block has been seen before, so it is NOT compulsory.
        if not actual_hit:
            # it's a miss in the real cache
            if fa_hit:
                # but it would have hit in a fully-associative cache
                # of the same size → conflict miss
                conflict += 1
            else:
                # would miss even with full associativity → capacity miss
                capacity += 1

    return {
        "compulsory": compulsory,
        "capacity":   capacity,
        "conflict":   conflict,
    }
