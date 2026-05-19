"""
traces/generators.py — Memory-access trace generators.
"""
 
from __future__ import annotations
import random
from typing import List
 
 
def gen_sequential(n: int = 4000, stride: int = 64, start: int = 0) -> List[int]:
    return [start + i * stride for i in range(n)]
 
 
def gen_random(n: int = 4000, addr_range: int = 1 << 22,
               block_size: int = 64, seed: int = 42) -> List[int]:
    rng = random.Random(seed)
    mask = ~(block_size - 1)
    return [rng.randint(0, addr_range) & mask for _ in range(n)]
 
 
def gen_matrix(rows: int = 64, cols: int = 64, elem_size: int = 8,
               num_matrices: int = 2) -> List[int]:
    addrs: List[int] = []
    bytes_per_matrix = rows * cols * elem_size
    for m in range(num_matrices):
        base = m * bytes_per_matrix
        for r in range(rows):
            for c in range(cols):
                addrs.append(base + (r * cols + c) * elem_size)
    return addrs
 
 
def gen_thrash(n: int = 4000, working_set: int = 1 << 17,
               block_size: int = 64, seed: int = 7) -> List[int]:
    rng = random.Random(seed)
    mask = ~(block_size - 1)
    return [rng.randint(0, working_set) & mask for _ in range(n)]
 
 
def gen_pointer_chase(n: int = 4000, addr_range: int = 1 << 22,
                      block_size: int = 64, seed: int = 11) -> List[int]:
    rng = random.Random(seed)
    mask = ~(block_size - 1)
    addr = 0
    out: List[int] = []
    for _ in range(n):
        addr = (addr + rng.randint(1, addr_range)) & (addr_range - 1) & mask
        out.append(addr)
    return out
 
 
_GENERATORS = {
    "sequential": lambda n: gen_sequential(n=n),
    "random":     lambda n: gen_random(n=n),
    "matrix":     lambda n: gen_matrix(),
    "thrash":     lambda n: gen_thrash(n=n),
    "pointer":    lambda n: gen_pointer_chase(n=n),
}
 
 
def list_traces() -> List[str]:
    return list(_GENERATORS)
 
 
def make_trace(name: str, n: int = 4000) -> List[int]:
    name = name.lower()
    if name not in _GENERATORS:
        raise ValueError(f"Unknown trace '{name}'. Available: {list(_GENERATORS)}")
    return _GENERATORS[name](n)
 