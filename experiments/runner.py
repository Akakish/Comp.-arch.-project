"""
experiments/runner.py
Author: Person #3

Sweep helpers для экспериментов.
Каждая функция принимает trace (list[int]) и возвращает данные
в формате, который ожидает viz/visualizer.py.
"""

from __future__ import annotations
from typing import Dict, List, Tuple

from core import CacheLevel, CacheHierarchy


def _run(cache: CacheLevel, trace: List[int]) -> None:
    """Прогоняем trace через один уровень кэша."""
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
    """
    Меняем размер кэша, фиксируем hit rate для каждой политики.
    Возвращает (sizes, {policy: [hit_rate, ...]}).
    """
    result: Dict[str, List[float]] = {p: [] for p in policies}
    for policy in policies:
        for sz in sizes:
            c = CacheLevel("L1", sz, assoc, block_size, policy)
            _run(c, trace)
            result[policy].append(c.stats.hit_rate)
    return list(sizes), result


def sweep_assoc(
    trace: List[int],
    assocs: List[int],
    policies: List[str] = ("LRU", "Clock", "RRIP"),
    size_bytes: int = 32 * 1024,
    block_size: int = 64,
) -> Tuple[List[int], Dict[str, List[float]]]:
    """
    Меняем ассоциативность, размер кэша фиксирован.
    Возвращает (assocs, {policy: [hit_rate, ...]}).
    """
    result: Dict[str, List[float]] = {p: [] for p in policies}
    for policy in policies:
        for a in assocs:
            c = CacheLevel("L1", size_bytes, a, block_size, policy)
            _run(c, trace)
            result[policy].append(c.stats.hit_rate)
    return list(assocs), result


def compare_policies(
    trace: List[int],
    policies: List[str] = ("LRU", "Clock", "RRIP"),
    size_bytes: int = 32 * 1024,
    assoc: int = 4,
    block_size: int = 64,
) -> Tuple[List[str], List[float]]:
    """
    Сравниваем политики на одной конфигурации кэша.
    Возвращает (policies, [hit_rate, ...]).
    """
    rates: List[float] = []
    for p in policies:
        c = CacheLevel("L1", size_bytes, assoc, block_size, p)
        _run(c, trace)
        rates.append(c.stats.hit_rate)
    return list(policies), rates


def heatmap_size_x_assoc(
    trace: List[int],
    sizes: List[int],
    assocs: List[int],
    policy: str = "LRU",
    block_size: int = 64,
) -> Tuple[List[int], List[int], List[List[float]]]:
    """
    2D sweep: размер × ассоциативность.
    Возвращает (sizes, assocs, miss_rate_matrix[size_idx][assoc_idx]).
    """
    matrix: List[List[float]] = []
    for sz in sizes:
        row: List[float] = []
        for a in assocs:
            # вырожденная конфигурация — считаем за 100% miss
            if sz // (a * block_size) < 1:
                row.append(1.0)
                continue
            c = CacheLevel("L1", sz, a, block_size, policy)
            _run(c, trace)
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
    """
    Прогоняем trace через иерархию L1→L2→L3.
    Возвращает статистику по каждому уровню + summary.
    Формат совместим с plot_multilevel_stats из viz/visualizer.py.
    """
    h = CacheHierarchy(
        l1_size=l1_size, l1_assoc=l1_assoc, l1_block=block_size, l1_policy=policy,
        l2_size=l2_size, l2_assoc=l2_assoc, l2_block=block_size, l2_policy=policy,
        l3_size=l3_size, l3_assoc=l3_assoc, l3_block=block_size, l3_policy=policy,
    )
    for addr in trace:
        h.access(addr)

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
