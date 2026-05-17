"""
core/block.py — Cache line (block) representation.
Author: Person #1 (core)
"""


class CacheBlock:
    """A single cache line stored inside a set."""

    def __init__(self, tag: int, data: int = 0):
        self.tag: int = tag          # address tag
        self.data: int = data        # placeholder for block data
        self.valid: bool = True
        self.dirty: bool = False     # for write-back policy (future work)
        self.rrpv: int = 3           # used by RRIP policy (max = 3)
        self.ref_bit: bool = True    # used by Clock policy

    def __repr__(self) -> str:
        return f"CacheBlock(tag={self.tag:#010x}, dirty={self.dirty})"
