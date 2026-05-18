"""
viz/demo.py — Quick demo of all visualization functions.
Run from project root:  python -m viz.demo
Author: Person #4 (viz)

This script wires the core (CacheLevel) to the viz module.
It runs small synthetic traces and produces all 6 chart types.
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.cache_level import CacheLevel
from viz.visualizer import (
    plot_hit_rate_vs_size,
    plot_hit_rate_vs_assoc,
    plot_hit_rate_vs_policy,
    plot_3c_breakdown,
    plot_miss_rate_heatmap,
    plot_multilevel_stats,
    save_figure,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def run_trace(cache: CacheLevel, addrs: list[int]) -> None:
    """Feed a list of addresses into the cache."""
    cache.flush()
    for addr in addrs:
        cache.access(addr)


def make_trace_sequential(n=2000, stride=64) -> list[int]:
    return [i * stride for i in range(n)]


def make_trace_random(n=2000, addr_range=1 << 20) -> list[int]:
    import random; random.seed(42)
    return [random.randint(0, addr_range) & ~63 for _ in range(n)]


def make_trace_thrash(n=2000, working_set=1 << 17) -> list[int]:
    """Accesses that thrash a given cache size."""
    import random; random.seed(7)
    return [random.randint(0, working_set) & ~63 for _ in range(n)]

# ─────────────────────────────────────────────────────────────────────────────
# 1. Hit rate vs cache size
# ─────────────────────────────────────────────────────────────────────────────

sizes = [4*1024, 8*1024, 16*1024, 32*1024, 64*1024, 128*1024]
trace = make_trace_random()

hit_rates_by_policy: dict[str, list[float]] = {"LRU": [], "Clock": [], "RRIP": []}

for policy in ["LRU", "Clock", "RRIP"]:
    for sz in sizes:
        c = CacheLevel("L1", sz, associativity=4, block_size=64, policy=policy)
        run_trace(c, trace)
        hit_rates_by_policy[policy].append(c.stats.hit_rate)

fig1 = plot_hit_rate_vs_size(sizes, hit_rates_by_policy)
save_figure(fig1, "viz/out_hit_rate_vs_size.png")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Hit rate vs associativity
# ─────────────────────────────────────────────────────────────────────────────

assocs = [1, 2, 4, 8, 16]
hit_rates_assoc: dict[str, list[float]] = {"LRU": [], "Clock": [], "RRIP": []}

for policy in ["LRU", "Clock", "RRIP"]:
    for a in assocs:
        c = CacheLevel("L1", 32*1024, associativity=a, block_size=64, policy=policy)
        run_trace(c, trace)
        hit_rates_assoc[policy].append(c.stats.hit_rate)

fig2 = plot_hit_rate_vs_assoc(assocs, hit_rates_assoc)
save_figure(fig2, "viz/out_hit_rate_vs_assoc.png")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Hit rate vs policy (bar chart)
# ─────────────────────────────────────────────────────────────────────────────

policies = ["LRU", "Clock", "RRIP"]
policy_rates = []
for p in policies:
    c = CacheLevel("L1", 32*1024, associativity=4, block_size=64, policy=p)
    run_trace(c, trace)
    policy_rates.append(c.stats.hit_rate)

fig3 = plot_hit_rate_vs_policy(policies, policy_rates, cache_label="L1 (32KB, 4-way)")
save_figure(fig3, "viz/out_policy_comparison.png")

# ─────────────────────────────────────────────────────────────────────────────
# 4. 3C breakdown  (imported from Person #2's analysis module if available,
#                   otherwise estimated here for demo purposes)
# ─────────────────────────────────────────────────────────────────────────────

try:
    # If Person #2's module exists, import real 3C data
    from traces.analysis import classify_3c  # type: ignore
    traces_dict = {
        "sequential": make_trace_sequential(),
        "random":     make_trace_random(),
        "thrash":     make_trace_thrash(),
    }
    comp_list, cap_list, conf_list, lbl_list = [], [], [], []
    for name, t in traces_dict.items():
        result = classify_3c(t, size_bytes=32*1024, associativity=4, block_size=64)
        comp_list.append(result["compulsory"])
        cap_list.append(result["capacity"])
        conf_list.append(result["conflict"])
        lbl_list.append(name)

except ImportError:
    # Fallback: estimated values for demo
    lbl_list  = ["sequential", "random", "thrash"]
    comp_list = [312,  890, 1200]
    cap_list  = [88,   430,  600]
    conf_list = [0,    180,  800]

fig4 = plot_3c_breakdown(lbl_list, comp_list, cap_list, conf_list)
save_figure(fig4, "viz/out_3c_breakdown.png")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Miss rate heatmap
# ─────────────────────────────────────────────────────────────────────────────

heatmap_sizes  = [4*1024, 8*1024, 16*1024, 32*1024, 64*1024]
heatmap_assocs = [1, 2, 4, 8]
miss_matrix    = []

for sz in heatmap_sizes:
    row = []
    for a in heatmap_assocs:
        c = CacheLevel("L1", sz, associativity=a, block_size=64, policy="LRU")
        run_trace(c, trace)
        row.append(c.stats.miss_rate)
    miss_matrix.append(row)

fig5 = plot_miss_rate_heatmap(heatmap_sizes, heatmap_assocs, miss_matrix)
save_figure(fig5, "viz/out_heatmap.png")

# ─────────────────────────────────────────────────────────────────────────────
# 6. Multi-level L1 → L2 → L3
# ─────────────────────────────────────────────────────────────────────────────

l3 = CacheLevel("L3", 512*1024, associativity=8,  block_size=64, policy="LRU")
l2 = CacheLevel("L2",  64*1024, associativity=4,  block_size=64, policy="LRU", next_level=l3)
l1 = CacheLevel("L1",  32*1024, associativity=4,  block_size=64, policy="LRU", next_level=l2)

# flush all
for lvl in [l1, l2, l3]:
    lvl.flush()
l2.next_level = l3
l1.next_level = l2

for addr in trace:
    l1.access(addr)

multilevel_stats = {
    "L1": {"hit_rate": l1.stats.hit_rate, "miss_rate": l1.stats.miss_rate,
           "hits": l1.stats.hits, "misses": l1.stats.misses, "accesses": l1.stats.accesses},
    "L2": {"hit_rate": l2.stats.hit_rate, "miss_rate": l2.stats.miss_rate,
           "hits": l2.stats.hits, "misses": l2.stats.misses, "accesses": l2.stats.accesses},
    "L3": {"hit_rate": l3.stats.hit_rate, "miss_rate": l3.stats.miss_rate,
           "hits": l3.stats.hits, "misses": l3.stats.misses, "accesses": l3.stats.accesses},
}

fig6 = plot_multilevel_stats(["L1", "L2", "L3"], multilevel_stats)
save_figure(fig6, "viz/out_multilevel.png")

print("\n[demo] All charts saved to viz/out_*.png")
print("[demo] To display interactively: import matplotlib.pyplot as plt; plt.show()")
