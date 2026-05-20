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

from .traces.generator import (
    sequential,
    random_trace,
    matrix,
    thrash,
    generate,
    save_trace,
    load_trace,
    save_trace_text,
    load_trace_text,
    GENERATORS,
)

from .analysis import (
    classify_3c,
    total_misses,
    miss_percentages,
    print_3c_report,
)

__all__ = [
    # generator
    "sequential",
    "random_trace",
    "matrix",
    "thrash",
    "generate",
    "save_trace",
    "load_trace",
    "save_trace_text",
    "load_trace_text",
    "GENERATORS",
    # analysis
    "classify_3c",
    "total_misses",
    "miss_percentages",
    "print_3c_report",
]
