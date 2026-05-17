"""
core/__init__.py — Public API for the cache simulator core.
Author: Person #1 (core)

Other team members import from here:
    from core import CacheHierarchy, CacheLevel, AccessResult
"""

from .block import CacheBlock
from .cache_level import CacheLevel, CacheStats
from .hierarchy import CacheHierarchy, AccessResult
from .policy import make_policy, POLICIES

__all__ = [
    "CacheBlock",
    "CacheLevel",
    "CacheStats",
    "CacheHierarchy",
    "AccessResult",
    "make_policy",
    "POLICIES",
]
