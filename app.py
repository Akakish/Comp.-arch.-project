"""
app.py — Streamlit dashboard for the Cache Hierarchy Simulator.
"""

from __future__ import annotations
import io
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import streamlit as st

from core import CacheHierarchy
from experiments import (
    compare_policies,
    heatmap_size_x_assoc,
    multilevel_stats,
    sweep_assoc,
    sweep_size,
)
from traces import classify_3c, list_traces, make_trace
from viz.visualizer import (
    plot_3c_breakdown,
    plot_hit_rate_vs_assoc,
    plot_hit_rate_vs_policy,
    plot_hit_rate_vs_size,
    plot_miss_rate_heatmap,
    plot_multilevel_stats,
)


PAGE_TITLE = "Cache Hierarchy Simulator"
TRACE_OPTIONS = list_traces()
POLICIES = ["LRU", "Clock", "RRIP"]
DEFAULT_SIZES = [4 * 1024, 8 * 1024, 16 * 1024, 32 * 1024, 64 * 1024,
                 128 * 1024, 256 * 1024, 512 * 1024, 1024 * 1024]
DEFAULT_ASSOCS = [1, 2, 4, 8, 16]


def _format_bytes(value: int) -> str:
    if value >= 1 << 20:
        return f"{value // (1 << 20)} MB"
    if value >= 1 << 10:
        return f"{value // (1 << 10)} KB"
    return f"{value} B"


def _render_hierarchy_diagram(
    l1_size: int,
    l1_assoc: int,
    l1_policy: str,
    l2_size: int,
    l2_assoc: int,
    l2_policy: str,
    l3_size: int,
    l3_assoc: int,
    l3_policy: str,
    block_size: int,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    boxes = [
        (0.05, 0.52, 0.25, 0.3, "L1 Cache"),
        (0.375, 0.52, 0.25, 0.3, "L2 Cache"),
        (0.7, 0.52, 0.25, 0.3, "L3 Cache"),
        (0.375, 0.12, 0.25, 0.2, "DRAM"),
    ]
    for x, y, w, h, label in boxes:
        rect = plt.Rectangle((x, y), w, h,
                             facecolor="#1F293A",
                             edgecolor="#8FA6C9",
                             linewidth=2,
                             zorder=1)
        ax.add_patch(rect)
        # Place label above the box instead of inside
        label_y = y + h + 0.05
        ax.text(x + w / 2, label_y, label,
                ha="center", va="bottom", fontsize=12,
                color="#F8FAFC", weight="bold")

    connectors = [
        ((0.3, 0.65), (0.375, 0.65)),
        ((0.625, 0.65), (0.7, 0.65)),
        ((0.5, 0.52), (0.5, 0.32)),
    ]
    for start, end in connectors:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops=dict(arrowstyle="->", color="#A5B4FC", lw=2),
        )

    level_texts = [
        f"size={_format_bytes(l1_size)}\n{l1_assoc}-way\n{l1_policy}\nblock={block_size}",
        f"size={_format_bytes(l2_size)}\n{l2_assoc}-way\n{l2_policy}\nblock={block_size}",
        f"size={_format_bytes(l3_size)}\n{l3_assoc}-way\n{l3_policy}\nblock={block_size}",
        "Latency path:\nL1 → L2 → L3 → DRAM\n4 / 12 / 40 / 200 cycles",
    ]

    for (x, y, w, h, _), text in zip(boxes, level_texts):
        ax.text(x + w / 2, y + h * 0.55,
                text,
                ha="center", va="center", color="#E2E8F0",
                fontsize=9, linespacing=1.2)

    fig.patch.set_facecolor("#0B1120")
    ax.set_facecolor("#0B1120")
    fig.tight_layout()
    return fig


def _render_access_animation(
    trace: List[int],
    l1_size: int,
    l1_assoc: int,
    l2_size: int,
    l2_assoc: int,
    l3_size: int,
    l3_assoc: int,
    block_size: int,
    policy: str,
    max_frames: int = 80,
) -> Optional[bytes]:
    try:
        from matplotlib.animation import FuncAnimation
        from matplotlib.animation import PillowWriter
    except ImportError:
        return None

    h = CacheHierarchy(
        l1_size=l1_size, l1_assoc=l1_assoc, l1_block=block_size, l1_policy=policy,
        l2_size=l2_size, l2_assoc=l2_assoc, l2_block=block_size, l2_policy=policy,
        l3_size=l3_size, l3_assoc=l3_assoc, l3_block=block_size, l3_policy=policy,
    )

    total = len(trace)
    if total == 0:
        return None

    step = max(1, total // max_frames)
    frames: List[Tuple[int, float]] = []

    for index, addr in enumerate(trace, start=1):
        h.access(addr)
        if index == total or index % step == 0:
            hit_rate = 1.0 - h.dram_accesses / index
            frames.append((index, hit_rate))

    if len(frames) < 2:
        return None

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_facecolor("#111827")
    fig.patch.set_facecolor("#111827")

    indices = [frame[0] for frame in frames]
    values = [frame[1] * 100.0 for frame in frames]
    line, = ax.plot([], [], color="#38BDF8", lw=2)
    dot, = ax.plot([], [], "o", color="#FACC15")
    ax.set_xlim(0, total)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Accesses")
    ax.set_ylabel("Overall hit rate (%)")
    ax.set_title("Hit-rate evolution during trace execution")
    ax.grid(color="#4B5563", linestyle="--", alpha=0.5)

    def update(frame_index: int):
        x = indices[: frame_index + 1]
        y = values[: frame_index + 1]
        line.set_data(x, y)
        dot.set_data(x[-1:], y[-1:])
        return line, dot

    anim = FuncAnimation(fig, update, frames=len(indices), interval=80, blit=True)
    buffer = io.BytesIO()
    anim.save(buffer, writer=PillowWriter(fps=10), dpi=100)
    buffer.seek(0)
    return buffer.read()


@st.cache_data
def _cached_trace(trace_name: str, length: int) -> List[int]:
    return make_trace(trace_name, n=length)


def _show_fig(fig: plt.Figure) -> None:
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)


def main() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="💾",
        layout="wide",
    )

    st.title("Cache Hierarchy Simulator")
    st.markdown(
        """
        **Interactive Python dashboard** for exploring and demonstrating
        the behavior of a multi-level cache hierarchy. Adjust sizes,
        associativity, replacement policies and trace patterns to see
        how hits, misses and latencies change.
        """
    )
    st.markdown(
        """
        ### How to use
        1. Select a trace and length.
        2. Configure L1/L2/L3 parameters.
        3. Choose a visualization mode.
        4. Click "Run simulation".
        5. View charts and metrics on the right.
        """
    )

    with st.sidebar.form(key="config_form"):
        st.subheader("Simulation settings")
        trace_name = st.selectbox("Trace", TRACE_OPTIONS, index=TRACE_OPTIONS.index("random"))
        trace_length = st.slider("Trace length", min_value=200, max_value=10000, step=200, value=4000)
        block_size = st.selectbox("Cache line size", [16, 32, 64, 128], index=2)

        mode = st.selectbox(
            "Режим визуализации",
            [
                "Multilevel hierarchy",
                "Cache size sweep",
                "Associativity sweep",
                "Policy comparison",
                "Heatmap",
                "3C breakdown",
                "Access animation",
            ],
        )

        st.markdown("---")
        st.subheader("Level parameters")
        l1_size = st.selectbox("L1 size", DEFAULT_SIZES, index=3)
        l1_assoc = st.selectbox("L1 associativity", DEFAULT_ASSOCS, index=2)
        l1_policy = st.selectbox("L1 policy", POLICIES, index=0)

        l2_size = st.selectbox("L2 size", DEFAULT_SIZES, index=5)
        l2_assoc = st.selectbox("L2 associativity", DEFAULT_ASSOCS, index=3)
        l2_policy = st.selectbox("L2 policy", POLICIES, index=0)

        l3_size = st.selectbox("L3 size", DEFAULT_SIZES, index=8)
        l3_assoc = st.selectbox("L3 associativity", DEFAULT_ASSOCS, index=4)
        l3_policy = st.selectbox("L3 policy", POLICIES, index=0)

        extra_sizes = st.multiselect(
            "Sizes for sweep / heatmap",
            DEFAULT_SIZES,
            default=[4 * 1024, 16 * 1024, 64 * 1024, 256 * 1024, 1024 * 1024],
        )
        extra_assocs = st.multiselect(
            "Associativities for sweep / heatmap",
            DEFAULT_ASSOCS,
            default=[1, 2, 4, 8, 16],
        )

        submitted = st.form_submit_button("Run simulation")

    if not submitted:
        st.info("Configure parameters on the left and click 'Run simulation'.")
        diagram_fig = _render_hierarchy_diagram(
            l1_size, l1_assoc, l1_policy,
            l2_size, l2_assoc, l2_policy,
            l3_size, l3_assoc, l3_policy,
            block_size,
        )
        st.pyplot(diagram_fig)
        return

    trace = _cached_trace(trace_name, trace_length)
    st.success(f"Trace '{trace_name}' ready: {len(trace)} accesses")

    left, right = st.columns([2, 1])
    with left:
        st.subheader("Cache hierarchy")
        _show_fig(_render_hierarchy_diagram(
            l1_size, l1_assoc, l1_policy,
            l2_size, l2_assoc, l2_policy,
            l3_size, l3_assoc, l3_policy,
            block_size,
        ))

        if mode == "Multilevel hierarchy":
            stats = multilevel_stats(
                trace,
                l1_size=l1_size, l1_assoc=l1_assoc,
                l2_size=l2_size, l2_assoc=l2_assoc,
                l3_size=l3_size, l3_assoc=l3_assoc,
                block_size=block_size,
                policy=l1_policy,
            )
            summary = stats["__summary__"]
            _show_fig(plot_multilevel_stats(["L1", "L2", "L3"], stats,
                                            title=f"Multilevel stats · {trace_name}"))
            st.metric("Avg latency", f"{summary['avg_latency_cycles']:.2f} cycles")
            st.metric("MPKI", f"{summary['MPKI']:.2f}")
            st.table({
                "L1 hit rate": f"{stats['L1']['hit_rate']*100:.2f}%",
                "L2 hit rate": f"{stats['L2']['hit_rate']*100:.2f}%",
                "L3 hit rate": f"{stats['L3']['hit_rate']*100:.2f}%",
            }, )

        elif mode == "Cache size sweep":
            if len(extra_sizes) < 2:
                st.warning("Select at least two sizes for the sweep.")
            else:
                sizes, hit_rates = sweep_size(
                    trace,
                    sorted(extra_sizes),
                    policies=POLICIES,
                    assoc=l1_assoc,
                    block_size=block_size,
                )
                _show_fig(plot_hit_rate_vs_size(sizes, hit_rates,
                                                title=f"Hit rate vs size · {trace_name}"))

        elif mode == "Associativity sweep":
            if len(extra_assocs) < 2:
                st.warning("Select at least two associativity values.")
            else:
                assocs, hit_rates = sweep_assoc(
                    trace,
                    sorted(extra_assocs),
                    policies=POLICIES,
                    size_bytes=l1_size,
                    block_size=block_size,
                )
                _show_fig(plot_hit_rate_vs_assoc(assocs, hit_rates,
                                                 title=f"Hit rate vs associativity · {trace_name}"))

        elif mode == "Policy comparison":
            policies, rates = compare_policies(
                trace,
                policies=POLICIES,
                size_bytes=l1_size,
                assoc=l1_assoc,
                block_size=block_size,
            )
            _show_fig(plot_hit_rate_vs_policy(policies, rates,
                                              cache_label="L1",
                                              title=f"Policy comparison · {trace_name}"))

        elif mode == "Heatmap":
            if len(extra_sizes) < 2 or len(extra_assocs) < 2:
                st.warning("Select at least two sizes and two associativities for the heatmap.")
            else:
                sizes, assocs, matrix = heatmap_size_x_assoc(
                    trace,
                    sorted(extra_sizes),
                    sorted(extra_assocs),
                    policy=l1_policy,
                    block_size=block_size,
                )
                _show_fig(plot_miss_rate_heatmap(sizes, assocs, matrix,
                                                 title=f"Miss rate heatmap · {trace_name}"))

        elif mode == "3C breakdown":
            result = classify_3c(trace, l1_size, l1_assoc, block_size)
            _show_fig(plot_3c_breakdown(
                [trace_name],
                [result["compulsory"]],
                [result["capacity"]],
                [result["conflict"]],
                title=f"3C breakdown · {trace_name}",
            ))
            total = sum(result.values())
            st.markdown(
                f"**Compulsory:** {result['compulsory']:,}  \
                **Capacity:** {result['capacity']:,}  \
                **Conflict:** {result['conflict']:,}  \
                **Total misses:** {total:,}"
            )

        elif mode == "Access animation":
            st.markdown("_Generating hit-rate animation as the trace executes._")
            gif_bytes = _render_access_animation(
                trace,
                l1_size, l1_assoc,
                l2_size, l2_assoc,
                l3_size, l3_assoc,
                block_size,
                l1_policy,
            )
            if gif_bytes is None:
                st.error("Animation unavailable. Install pillow and run again.")
            else:
                st.image(gif_bytes, format="GIF")

    with right:
        st.subheader("Trace parameters")
        st.write(f"**Type:** {trace_name}")
        st.write(f"**Length:** {len(trace)}")
        st.write(f"**Block size:** {block_size} B")
        st.markdown("---")
        st.subheader("Available modes")
        st.markdown(
            "- Multilevel hierarchy: final metrics for L1/L2/L3 + MPKI\n"
            "- Cache size sweep: compare hit-rate across sizes\n"
            "- Associativity sweep: compare hit-rate across associativities\n"
            "- Policy comparison: LRU / Clock / RRIP\n"
            "- Heatmap: miss rate vs size and associativity\n"
            "- 3C breakdown: classify misses as Compulsory/Capacity/Conflict\n"
        )

    st.markdown("---")
    st.caption(
        "This app uses the existing core/ and traces/ modules in the project"
        " for accurate cache-hierarchy simulation."
    )


if __name__ == "__main__":
    main()
