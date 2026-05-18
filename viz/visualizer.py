"""
viz/visualizer.py — Visualization module for Cache Hierarchy Simulator.
Author: Person #4 (viz)

Provides:
    plot_hit_rate_vs_size()       — hit rate as cache size varies
    plot_hit_rate_vs_assoc()      — hit rate as associativity varies
    plot_hit_rate_vs_policy()     — bar chart comparing LRU / Clock / RRIP
    plot_3c_breakdown()           — stacked bar: Compulsory/Capacity/Conflict
    plot_miss_rate_heatmap()      — 2-D heatmap: size × associativity
    plot_multilevel_stats()       — grouped bars for L1 / L2 / L3

All functions accept data produced by the core and return matplotlib Figure
objects so the CLI (main.py) can either show() or save() them.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── Palette ──────────────────────────────────────────────────────────────────
_COLORS = {
    "blue":    "#4A90D9",
    "orange":  "#F5A623",
    "green":   "#7ED321",
    "red":     "#D0021B",
    "purple":  "#9B59B6",
    "teal":    "#1ABC9C",
    "gray":    "#95A5A6",
    "dark":    "#2C3E50",
}
_POLICY_COLORS = {
    "LRU":   _COLORS["blue"],
    "Clock": _COLORS["orange"],
    "RRIP":  _COLORS["green"],
}
_3C_COLORS = {
    "Compulsory": _COLORS["red"],
    "Capacity":   _COLORS["orange"],
    "Conflict":   _COLORS["blue"],
}

_STYLE = {
    "figure.facecolor":  "#1E2430",
    "axes.facecolor":    "#252D3D",
    "axes.edgecolor":    "#3D4F6E",
    "axes.labelcolor":   "#CDD6F4",
    "axes.titlesize":    13,
    "axes.titleweight":  "bold",
    "axes.titlecolor":   "#CDD6F4",
    "axes.grid":         True,
    "grid.color":        "#3D4F6E",
    "grid.linestyle":    "--",
    "grid.alpha":        0.5,
    "xtick.color":       "#CDD6F4",
    "ytick.color":       "#CDD6F4",
    "text.color":        "#CDD6F4",
    "legend.facecolor":  "#2C3A52",
    "legend.edgecolor":  "#3D4F6E",
    "legend.labelcolor": "#CDD6F4",
    "lines.linewidth":   2.2,
    "lines.markersize":  7,
    "font.family":       "monospace",
}


def _apply_style():
    plt.rcParams.update(_STYLE)


def _bytes_label(b: int) -> str:
    """Human-readable size label: 1024 → '1 KB', 1048576 → '1 MB'."""
    if b >= 1 << 20:
        return f"{b >> 20} MB"
    if b >= 1 << 10:
        return f"{b >> 10} KB"
    return f"{b} B"


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Hit rate vs cache size
# ─────────────────────────────────────────────────────────────────────────────

def plot_hit_rate_vs_size(
    sizes: List[int],
    hit_rates: Dict[str, List[float]],   # {"LRU": [...], "Clock": [...], ...}
    title: str = "Hit Rate vs Cache Size",
) -> plt.Figure:
    """
    Line chart: x = cache size, y = hit rate, one line per policy.

    Parameters
    ----------
    sizes     : list of cache sizes in bytes, e.g. [4096, 8192, 16384, ...]
    hit_rates : dict mapping policy name → list of hit_rate values (0-1)
                length must match len(sizes)
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(9, 5))

    labels = [_bytes_label(s) for s in sizes]
    x = np.arange(len(sizes))

    for policy, rates in hit_rates.items():
        color = _POLICY_COLORS.get(policy, _COLORS["purple"])
        ax.plot(x, [r * 100 for r in rates],
                marker="o", label=policy, color=color)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax.set_ylabel("Hit Rate (%)")
    ax.set_xlabel("Cache Size")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Hit rate vs associativity
# ─────────────────────────────────────────────────────────────────────────────

def plot_hit_rate_vs_assoc(
    assocs: List[int],
    hit_rates: Dict[str, List[float]],
    title: str = "Hit Rate vs Associativity",
) -> plt.Figure:
    """
    Line chart: x = associativity (1, 2, 4, 8 …), y = hit rate.

    Parameters
    ----------
    assocs    : list of associativity values
    hit_rates : dict policy → list of hit_rate (0-1)
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 5))

    x = np.arange(len(assocs))
    labels = [f"{a}-way" if a > 1 else "Direct" for a in assocs]

    for policy, rates in hit_rates.items():
        color = _POLICY_COLORS.get(policy, _COLORS["purple"])
        ax.plot(x, [r * 100 for r in rates],
                marker="s", label=policy, color=color)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax.set_ylabel("Hit Rate (%)")
    ax.set_xlabel("Associativity")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Hit rate vs policy (bar chart)
# ─────────────────────────────────────────────────────────────────────────────

def plot_hit_rate_vs_policy(
    policies: List[str],
    hit_rates: List[float],
    cache_label: str = "L1",
    title: Optional[str] = None,
) -> plt.Figure:
    """
    Grouped or single bar chart comparing replacement policies.

    Parameters
    ----------
    policies   : e.g. ["LRU", "Clock", "RRIP"]
    hit_rates  : corresponding hit rates (0-1)
    cache_label: used in axis / title
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(7, 5))

    colors = [_POLICY_COLORS.get(p, _COLORS["purple"]) for p in policies]
    x = np.arange(len(policies))
    bars = ax.bar(x, [r * 100 for r in hit_rates], color=colors,
                  width=0.5, edgecolor="#1E2430", linewidth=1.2)

    for bar, rate in zip(bars, hit_rates):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.4,
                f"{rate*100:.2f}%",
                ha="center", va="bottom", fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels(policies)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.set_ylabel("Hit Rate (%)")
    ax.set_xlabel("Replacement Policy")
    ax.set_title(title or f"{cache_label} — Hit Rate by Replacement Policy")
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4.  3C breakdown (stacked bar)
# ─────────────────────────────────────────────────────────────────────────────

def plot_3c_breakdown(
    labels: List[str],
    compulsory: List[int],
    capacity: List[int],
    conflict: List[int],
    title: str = "3C Miss Classification",
) -> plt.Figure:
    """
    Stacked bar chart showing Compulsory / Capacity / Conflict miss counts.

    Parameters
    ----------
    labels      : x-axis labels (e.g. trace names or config names)
    compulsory  : cold-start miss counts per label
    capacity    : capacity miss counts per label
    conflict    : conflict miss counts per label
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(9, 5))

    x = np.arange(len(labels))
    comp = np.array(compulsory)
    cap  = np.array(capacity)
    conf = np.array(conflict)

    ax.bar(x, comp, label="Compulsory", color=_3C_COLORS["Compulsory"])
    ax.bar(x, cap,  bottom=comp,        label="Capacity",   color=_3C_COLORS["Capacity"])
    ax.bar(x, conf, bottom=comp + cap,  label="Conflict",   color=_3C_COLORS["Conflict"])

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Miss Count")
    ax.set_title(title)
    ax.legend()

    # Annotate totals on top
    totals = comp + cap + conf
    for xi, tot in zip(x, totals):
        ax.text(xi, tot + totals.max() * 0.01, f"{tot:,}",
                ha="center", va="bottom", fontsize=8)

    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Miss rate heatmap (size × associativity)
# ─────────────────────────────────────────────────────────────────────────────

def plot_miss_rate_heatmap(
    sizes: List[int],
    assocs: List[int],
    miss_rates: List[List[float]],   # [size_idx][assoc_idx]
    title: str = "Miss Rate Heatmap (Size × Associativity)",
) -> plt.Figure:
    """
    2-D heatmap where rows = cache sizes, columns = associativity values.

    Parameters
    ----------
    sizes      : list of cache sizes in bytes
    assocs     : list of associativity values
    miss_rates : 2-D list [len(sizes)][len(assocs)] of miss rates (0-1)
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 5))

    data = np.array(miss_rates) * 100   # → percentage
    im = ax.imshow(data, aspect="auto", cmap="YlOrRd",
                   vmin=0, vmax=max(data.max(), 1))

    ax.set_xticks(np.arange(len(assocs)))
    ax.set_xticklabels([f"{a}-way" if a > 1 else "DM" for a in assocs])
    ax.set_yticks(np.arange(len(sizes)))
    ax.set_yticklabels([_bytes_label(s) for s in sizes])
    ax.set_xlabel("Associativity")
    ax.set_ylabel("Cache Size")
    ax.set_title(title)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Miss Rate (%)", color="#CDD6F4")
    cbar.ax.yaxis.set_tick_params(color="#CDD6F4")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#CDD6F4")

    # Annotate cells
    for i in range(len(sizes)):
        for j in range(len(assocs)):
            ax.text(j, i, f"{data[i, j]:.1f}%",
                    ha="center", va="center",
                    color="black" if data[i, j] < 50 else "white",
                    fontsize=8)

    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Multi-level stats (L1 / L2 / L3 grouped bars)
# ─────────────────────────────────────────────────────────────────────────────

def plot_multilevel_stats(
    levels: List[str],
    stats: Dict[str, Dict],   # {"L1": {"hit_rate": 0.9, "misses": 100}, ...}
    title: str = "Cache Hierarchy Statistics",
) -> plt.Figure:
    """
    Side-by-side bars showing hit_rate and miss_rate for each cache level.

    Parameters
    ----------
    levels : e.g. ["L1", "L2", "L3"]
    stats  : dict level → CacheStats-like dict with keys
             'hit_rate', 'miss_rate', 'accesses', 'hits', 'misses'
    """
    _apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    fig.suptitle(title, fontsize=14, fontweight="bold")

    level_colors = [_COLORS["blue"], _COLORS["orange"], _COLORS["green"]]
    x = np.arange(len(levels))

    # ── Left: hit rate ──
    ax = axes[0]
    hit_rates = [stats[l]["hit_rate"] * 100 for l in levels]
    bars = ax.bar(x, hit_rates,
                  color=level_colors[:len(levels)],
                  edgecolor="#1E2430", linewidth=1.2)
    for bar, val in zip(bars, hit_rates):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(levels)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.set_ylabel("Hit Rate (%)")
    ax.set_title("Hit Rate per Level")
    ax.set_ylim(0, 105)

    # ── Right: absolute counts ──
    ax2 = axes[1]
    hits   = [stats[l]["hits"]   for l in levels]
    misses = [stats[l]["misses"] for l in levels]
    w = 0.35
    ax2.bar(x - w/2, hits,   width=w, label="Hits",   color=_COLORS["teal"],   edgecolor="#1E2430")
    ax2.bar(x + w/2, misses, width=w, label="Misses", color=_COLORS["red"],    edgecolor="#1E2430")
    ax2.set_xticks(x)
    ax2.set_xticklabels(levels)
    ax2.set_ylabel("Count")
    ax2.set_title("Hits vs Misses per Level")
    ax2.legend()

    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: save or show
# ─────────────────────────────────────────────────────────────────────────────

def save_figure(fig: plt.Figure, path: str, dpi: int = 150) -> None:
    """Save a figure to *path* (PNG, PDF, SVG …)."""
    fig.savefig(path, dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    print(f"[viz] Saved → {path}")


def show_all(figs: List[plt.Figure]) -> None:
    """Display all figures. Call after all plots are created."""
    plt.show()
