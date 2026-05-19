"""
experiments/runner.py — Sweep-experiment helpers.
Author: Person #3 (CLI & experiments)
"""

from __future__ import annotations
from typing import Dict, List, Tuple

from core import CacheLevel, CacheHierarchy


def _run_single(cache: CacheLevel, trace: List[int]) -> None:
    cache.flush()
    for addr in trace:
        cache.access(addr)


def sweep_size(
    trace: List[int],
    sizes: List[int],
    policies: List[str] = ("LRU", "Clock", "RRIP"),
    assoc: int = 4,
    block_size: int = 64,
) -> Tuple[List[int], Dict[str, List[float]]]:
    hit_rates_by_policy: Dict[str, List[float]] = {p: [] for p in policies}
    for policy in policies:
        for sz in sizes:
            c = CacheLevel("L1", sz, assoc, block_size, policy)
            _run_single(c, trace)
            hit_rates_by_policy[policy].append(c.stats.hit_rate)
    return list(sizes), hit_rates_by_policy


def sweep_assoc(
    trace: List[int],
    assocs: List[int],
    policies: List[str] = ("LRU", "Clock", "RRIP"),
    size_bytes: int = 32 * 1024,
    block_size: int = 64,
) -> Tuple[List[int], Dict[str, List[float]]]:
    hit_rates_by_policy: Dict[str, List[float]] = {p: [] for p in policies}
    for policy in policies:
        for a in assocs:
            c = CacheLevel("L1", size_bytes, a, block_size, policy)
            _run_single(c, trace)
            hit_rates_by_policy[policy].append(c.stats.hit_rate)
    return list(assocs), hit_rates_by_policy


def compare_policies(
    trace: List[int],
    policies: List[str] = ("LRU", "Clock", "RRIP"),
    size_bytes: int = 32 * 1024,
    assoc: int = 4,
    block_size: int = 64,
) -> Tuple[List[str], List[float]]:
    rates: List[float] = []
    for p in policies:
        c = CacheLevel("L1", size_bytes, assoc, block_size, p)
        _run_single(c, trace)
        rates.append(c.stats.hit_rate)
    return list(policies), rates


def heatmap_size_x_assoc(
    trace: List[int],
    sizes: List[int],
    assocs: List[int],
    policy: str = "LRU",
    block_size: int = 64,
) -> Tuple[List[int], List[int], List[List[float]]]:
    matrix: List[List[float]] = []
    for sz in sizes:
        row: List[float] = []
        for a in assocs:
            if sz // (a * block_size) < 1:
                row.append(1.0)
                continue
            c = CacheLevel("L1", sz, a, block_size, policy)
            _run_single(c, trace)
            row.append(c.stats.miss_rate)
        matrix.append(row)
    return list(sizes), list(assocs), matrix


def multilevel_stats(
    trace: List[int],
    l1_size: int = 32 * 1024,  l1_assoc: int = 4,
    l2_size: int = 256 * 1024, l2_assoc: int = 8,
    l3_size: int = 8 * 1024 * 1024, l3_assoc: int = 16,
    block_size: int = 64,
    policy: str = "LRU",
) -> Dict[str, Dict[str, float]]:
    h = CacheHierarchy(
        l1_size=l1_size, l1_assoc=l1_assoc, l1_block=block_size, l1_policy=policy,
        l2_size=l2_size, l2_assoc=l2_assoc, l2_block=block_size, l2_policy=policy,
        l3_size=l3_size, l3_assoc=l3_assoc, l3_block=block_size, l3_policy=policy,
    )
    for a in trace:
        h.access(a)
    out: Dict[str, Dict[str, float]] = {}
    for lvl in h.levels:
        s = lvl.stats
        out[lvl.name] = {
            "hit_rate":  s.hit_rate,
            "miss_rate": s.miss_rate,
            "accesses":  s.accesses,
            "hits":      s.hits,
            "misses":    s.misses,
        }
    out["DRAM"] = {
        "hit_rate":  0.0,
        "miss_rate": 1.0,
        "accesses":  h.dram_accesses,
        "hits":      0,
        "misses":    h.dram_accesses,
    }
    out["__summary__"] = h.summary()
    return out
