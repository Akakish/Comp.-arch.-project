"""
traces/ — Memory-access trace generators and 3C miss classification.

Authors:
    Person #2 owns this module long-term. Person #3 provided rich
    stubs (in generators.py and analysis.py) so that CLI + viz work
    end-to-end before Person #2's final version lands.
"""

from .generators import (
    gen_sequential,
    gen_random,
    gen_matrix,
    gen_thrash,
    gen_pointer_chase,
    list_traces,
    make_trace,
)
from .analysis import classify_3c

__all__ = [
    "gen_sequential",
    "gen_random",
    "gen_matrix",
    "gen_thrash",
    "gen_pointer_chase",
    "list_traces",
    "make_trace",
    "classify_3c",
]
