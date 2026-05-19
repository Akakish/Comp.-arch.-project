"""
traces/analysis.py — 3C miss classification (Compulsory / Capacity / Conflict).
"""
 
from __future__ import annotations
from collections import OrderedDict
from typing import List, Dict
 
 
def _block_of(addr: int, block_size: int) -> int:
    return addr // block_size
 
 
class _FullyAssocLRU:
    def __init__(self, nblocks: int):
        self.nblocks = max(1, nblocks)
        self._od: OrderedDict = OrderedDict()
 
    def access(self, block_id: int) -> bool:
        if block_id in self._od:
            self._od.move_to_end(block_id)
            return True
        self._od[block_id] = None
        if len(self._od) > self.nblocks:
            self._od.popitem(last=False)
        return False
 
 
class _SetAssocLRU:
    def __init__(self, size_bytes: int, associativity: int, block_size: int):
        num_sets = max(1, size_bytes // (associativity * block_size))
        self.num_sets = num_sets
        self.assoc = associativity
        self.block = block_size
        self._sets: List[OrderedDict] = [OrderedDict() for _ in range(num_sets)]
 
    def _parse(self, block_id: int):
        set_idx = block_id % self.num_sets
        tag = block_id // self.num_sets
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
 
 
def classify_3c(
    addrs: List[int],
    size_bytes: int,
    associativity: int,
    block_size: int,
) -> Dict[str, int]:
    if not addrs:
        return {"compulsory": 0, "capacity": 0, "conflict": 0}
 
    nblocks = max(1, size_bytes // block_size)
    actual = _SetAssocLRU(size_bytes, associativity, block_size)
    fa = _FullyAssocLRU(nblocks)
 
    seen_blocks: set = set()
    compulsory = 0
    capacity = 0
    conflict = 0
 
    for a in addrs:
        b = _block_of(a, block_size)
        actual_hit = actual.access(b)
        fa_hit = fa.access(b)
 
        if b not in seen_blocks:
            seen_blocks.add(b)
            compulsory += 1
            continue
 
        if not actual_hit:
            if fa_hit:
                conflict += 1
            else:
                capacity += 1
 
    return {"compulsory": compulsory, "capacity": capacity, "conflict": conflict}