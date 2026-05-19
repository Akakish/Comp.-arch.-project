"""
traces/ — Memory-access trace generators and 3C miss classification.
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