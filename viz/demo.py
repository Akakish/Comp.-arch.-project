"""
viz/demo.py — Demo that uses main.py experiments to show charts.
Author: Person #4 (viz)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib.pyplot as plt
from viz.visualizer import (
    plot_hit_rate_vs_size,
    plot_hit_rate_vs_assoc,
    plot_hit_rate_vs_policy,
    plot_3c_breakdown,
    plot_miss_rate_heatmap,
    plot_multilevel_stats,
)
from traces import make_trace
from experiments import (
    sweep_size, sweep_assoc, compare_policies,
    heatmap_size_x_assoc, multilevel_stats
)

trace = make_trace("random", n=2000)

# Person #3 считает → я рисую
sizes = [4*1024, 8*1024, 16*1024, 32*1024, 64*1024, 128*1024]
s, hr = sweep_size(trace, sizes)
fig1 = plot_hit_rate_vs_size(s, hr)

assocs = [1, 2, 4, 8, 16]
a, ha = sweep_assoc(trace, assocs)
fig2 = plot_hit_rate_vs_assoc(a, ha)

p, pr = compare_policies(trace)
fig3 = plot_hit_rate_vs_policy(p, pr)

from traces import classify_3c
traces_names = ["sequential", "random", "thrash"]
comp, cap, conf = [], [], []
for name in traces_names:
    t = make_trace(name)
    r = classify_3c(t, 32*1024, 4, 64)
    comp.append(r["compulsory"])
    cap.append(r["capacity"])
    conf.append(r["conflict"])
fig4 = plot_3c_breakdown(traces_names, comp, cap, conf)

sz, ac, mx = heatmap_size_x_assoc(trace, sizes[:5], [1,2,4,8])
fig5 = plot_miss_rate_heatmap(sz, ac, mx)

ms = multilevel_stats(trace)
per_lvl = {k: v for k, v in ms.items() if k in ("L1","L2","L3")}
fig6 = plot_multilevel_stats(["L1","L2","L3"], per_lvl)

print("✓ Done! Opening all 6 charts...")
plt.show()
