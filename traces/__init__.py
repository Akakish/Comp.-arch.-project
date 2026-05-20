"""
traces/
-------
Генерация трасс и 3C-классификация промахов кэша.

Быстрый старт:
    from traces.generator import generate
    from traces.analysis import classify_3c, print_3c_report

    addrs = generate("sequential", num_accesses=4096)
    result = classify_3c(addrs, size_bytes=32*1024, associativity=4, block_size=64)
    print_3c_report(result, total_accesses=len(addrs))
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

from .analysis import (
    classify_3c,
    total_misses,
    miss_percentages,
    print_3c_report,
)

__all__ = [
    # generator helpers
    "gen_sequential",
    "gen_random",
    "gen_matrix",
    "gen_thrash",
    "gen_pointer_chase",
    "list_traces",
    "make_trace",
    # analysis
    "classify_3c",
    "total_misses",
    "miss_percentages",
    "print_3c_report",
]
