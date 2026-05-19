"""
traces/generators.py — Memory-access trace generators.

NOTE for Person #2:
    Эти генераторы — рабочие заглушки, написанные Person #3, чтобы CLI
    и визуализация работали прямо сейчас. Можешь расширить, заменить,
    или импортировать их из своего модуля — главное, чтобы CLI продолжал
    видеть импорты из traces (`make_trace`, либо отдельные функции).

Trace = list[int] (a list of byte addresses).

Built-in patterns:
    sequential : addresses 0, stride, 2*stride, ...
    random     : uniformly random addresses (block-aligned) in a range
    matrix     : row-major scan of two matrices (good for L1, bad for L2)
    thrash     : tight working set repeatedly hammered — exposes capacity misses
    stride     : a configurable stride pattern (alias for sequential with stride)
    pointer    : pointer-chasing-like random walk (cache-unfriendly)
"""

from __future__ import annotations
import random
from typing import List


# ─── individual generators ───────────────────────────────────────────────

def gen_sequential(n: int = 4000, stride: int = 64,
                   start: int = 0) -> List[int]:
    """addresses 0, stride, 2*stride, …  (great for prefetcher / L1 hits)."""
    return [start + i * stride for i in range(n)]


def gen_random(n: int = 4000, addr_range: int = 1 << 22,
               block_size: int = 64, seed: int = 42) -> List[int]:
    """uniformly random block-aligned addresses."""
    rng = random.Random(seed)
    mask = ~(block_size - 1)
    return [rng.randint(0, addr_range) & mask for _ in range(n)]


def gen_matrix(rows: int = 64, cols: int = 64, elem_size: int = 8,
               num_matrices: int = 2) -> List[int]:
    """
    Row-major scan of `num_matrices` matrices (rows × cols, 8-byte elements).
    Mimics a naive matmul read pattern.
    """
    addrs: List[int] = []
    base_a = 0
    bytes_per_matrix = rows * cols * elem_size
    for m in range(num_matrices):
        base = base_a + m * bytes_per_matrix
        for r in range(rows):
            for c in range(cols):
                addrs.append(base + (r * cols + c) * elem_size)
    return addrs


def gen_thrash(n: int = 4000, working_set: int = 1 << 17,
               block_size: int = 64, seed: int = 7) -> List[int]:
    """
    Tight, randomly addressed working set that does NOT fit in L1.
    Designed to maximise capacity misses.
    """
    rng = random.Random(seed)
    mask = ~(block_size - 1)
    return [rng.randint(0, working_set) & mask for _ in range(n)]


def gen_pointer_chase(n: int = 4000, addr_range: int = 1 << 22,
                      block_size: int = 64, seed: int = 11) -> List[int]:
    """
    Pseudo pointer-chasing: each address is a random offset relative to the
    previous one — kills spatial locality and most prefetchers.
    """
    rng = random.Random(seed)
    mask = ~(block_size - 1)
    addr = 0
    out: List[int] = []
    for _ in range(n):
        addr = (addr + rng.randint(1, addr_range)) & (addr_range - 1) & mask
        out.append(addr)
    return out


# ─── dispatcher ──────────────────────────────────────────────────────────

_GENERATORS = {
    "sequential":     lambda n: gen_sequential(n=n),
    "random":         lambda n: gen_random(n=n),
    "matrix":         lambda n: gen_matrix(),               # n is implicit
    "thrash":         lambda n: gen_thrash(n=n),
    "pointer":        lambda n: gen_pointer_chase(n=n),
}


def list_traces() -> List[str]:
    """Names of all built-in traces."""
    return list(_GENERATORS)


def make_trace(name: str, n: int = 4000) -> List[int]:
    """Build a trace by name."""
    name = name.lower()
    if name not in _GENERATORS:
        raise ValueError(
            f"Unknown trace '{name}'. Available: {list(_GENERATORS)}"
        )
    return _GENERATORS[name](n)
