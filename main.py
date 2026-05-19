"""
main.py — Command-line interface for the Cache Hierarchy Simulator.
Author: Person #3 (CLI & experiments)

Examples
--------

    # Run a single trace through a single L1 cache:
    python main.py single --l1-size 32k --policy LRU --trace random

    # Run a trace through the full L1→L2→L3 hierarchy:
    python main.py multilevel --trace matrix

    # Sweep cache sizes from 4 KB to 1 MB (all 3 policies, default trace=random)
    python main.py sweep-size --sizes 4k,8k,16k,32k,64k,128k,256k,512k,1m --plot

    # Sweep associativity 1..16-way at a fixed 32 KB L1
    python main.py sweep-assoc --assocs 1,2,4,8,16 --plot

    # Compare LRU vs Clock vs RRIP at one config
    python main.py compare-policies --trace thrash --plot

    # 2-D heatmap: size × associativity
    python main.py heatmap --plot

    # 3C miss classification for several traces
    python main.py 3c --traces sequential,random,matrix,thrash --plot

    # Same as `python -m viz.demo` — runs the full visual demo
    python main.py demo

Tip: add  --save results/figures  to dump PNGs instead of opening them.
Tip: add  --json               to print machine-readable summary JSON.
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from typing import List, Dict

# ────────────────────────────────────────────────────────────────────────
# Local imports
# ────────────────────────────────────────────────────────────────────────

from core import CacheHierarchy, CacheLevel
from traces import make_trace, list_traces, classify_3c
from experiments import (
    sweep_size,
    sweep_assoc,
    compare_policies,
    heatmap_size_x_assoc,
    multilevel_stats,
)

# matplotlib is imported lazily inside each command so `--help` is fast


# ────────────────────────────────────────────────────────────────────────
# Pretty printing helpers
# ────────────────────────────────────────────────────────────────────────

_BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║          CACHE HIERARCHY SIMULATOR · Topic #8                    ║
║          Computer Architecture & OS  ·  Final Project            ║
╚══════════════════════════════════════════════════════════════════╝
"""


def _print_banner(quiet: bool) -> None:
    if not quiet:
        print(_BANNER)


def _print_kv(d: Dict, indent: int = 2) -> None:
    """Pretty-print a flat dict (key: value) with aligned columns."""
    if not d:
        print(" " * indent + "(empty)")
        return
    key_w = max(len(str(k)) for k in d.keys())
    pad = " " * indent
    for k, v in d.items():
        if isinstance(v, float):
            vs = f"{v:.4f}" if v < 1 else f"{v:.2f}"
        else:
            vs = str(v)
        print(f"{pad}{str(k).ljust(key_w)}  =  {vs}")


def _fmt_bytes(b: int) -> str:
    if b >= 1 << 20:
        return f"{b >> 20} MB"
    if b >= 1 << 10:
        return f"{b >> 10} KB"
    return f"{b} B"


# ────────────────────────────────────────────────────────────────────────
# Parsers for CLI arguments
# ────────────────────────────────────────────────────────────────────────

def _parse_size(s: str) -> int:
    """
    Parse a size string like '32k', '4MB', '512', '1g' into bytes.
    Accepts: <int>[k|kb|m|mb|g|gb]   (case-insensitive)
    """
    s = s.strip().lower().replace("_", "").replace(",", "")
    if not s:
        raise argparse.ArgumentTypeError("empty size")
    mult = 1
    if s.endswith("kb"):
        mult, s = 1024, s[:-2]
    elif s.endswith("mb"):
        mult, s = 1024 * 1024, s[:-2]
    elif s.endswith("gb"):
        mult, s = 1024 * 1024 * 1024, s[:-2]
    elif s.endswith("k"):
        mult, s = 1024, s[:-1]
    elif s.endswith("m"):
        mult, s = 1024 * 1024, s[:-1]
    elif s.endswith("g"):
        mult, s = 1024 * 1024 * 1024, s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad size '{s}'")


def _parse_size_list(s: str) -> List[int]:
    return [_parse_size(x) for x in s.split(",") if x.strip()]


def _parse_int_list(s: str) -> List[int]:
    return [int(x) for x in s.split(",") if x.strip()]


def _parse_str_list(s: str) -> List[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


# ────────────────────────────────────────────────────────────────────────
# Output helpers (save / show)
# ────────────────────────────────────────────────────────────────────────

def _handle_figure(fig, name: str, save_dir: str | None, show: bool) -> None:
    """Either save fig to save_dir/name.png or show it (or both)."""
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        from viz.visualizer import save_figure
        path = os.path.join(save_dir, f"{name}.png")
        save_figure(fig, path)
    if show:
        import matplotlib.pyplot as plt
        plt.show()


# ════════════════════════════════════════════════════════════════════════
# Commands
# ════════════════════════════════════════════════════════════════════════

def cmd_single(args: argparse.Namespace) -> None:
    """Run one trace through a single L1 cache and print stats."""
    trace = make_trace(args.trace, n=args.n)

    c = CacheLevel("L1", args.l1_size, args.assoc, args.block, args.policy)
    for a in trace:
        c.access(a)

    info = c.info()
    info["trace"]  = args.trace
    info["accesses"]   = c.stats.accesses
    info["hits"]       = c.stats.hits
    info["misses"]     = c.stats.misses
    info["hit_rate"]   = c.stats.hit_rate
    info["miss_rate"]  = c.stats.miss_rate
    info["evictions"]  = c.stats.evictions

    if args.json:
        print(json.dumps(info, indent=2))
        return

    print(f"┌─ Single-cache experiment ─{'─' * 40}")
    print(f"│  trace      : {args.trace} (n = {args.n})")
    print(f"│  cache      : L1 = {_fmt_bytes(args.l1_size)}, "
          f"{args.assoc}-way, {args.block} B blocks")
    print(f"│  policy     : {args.policy}")
    print(f"└{'─' * 60}")
    print()
    _print_kv({
        "accesses":  info["accesses"],
        "hits":      info["hits"],
        "misses":    info["misses"],
        "hit rate":  f"{info['hit_rate']*100:.2f} %",
        "miss rate": f"{info['miss_rate']*100:.2f} %",
        "evictions": info["evictions"],
    })


def cmd_multilevel(args: argparse.Namespace) -> None:
    """Run a trace through full L1→L2→L3 hierarchy."""
    trace = make_trace(args.trace, n=args.n)

    stats = multilevel_stats(
        trace,
        l1_size=args.l1_size, l1_assoc=args.l1_assoc,
        l2_size=args.l2_size, l2_assoc=args.l2_assoc,
        l3_size=args.l3_size, l3_assoc=args.l3_assoc,
        block_size=args.block,
        policy=args.policy,
    )
    summary = stats["__summary__"]

    if args.json:
        print(json.dumps({"per_level": {k: v for k, v in stats.items()
                                        if not k.startswith("__")},
                          "summary": summary}, indent=2))
    else:
        print(f"┌─ Multilevel experiment ─{'─' * 40}")
        print(f"│  trace : {args.trace} (n = {args.n}), policy = {args.policy}")
        print(f"│  L1    : {_fmt_bytes(args.l1_size)}, {args.l1_assoc}-way")
        print(f"│  L2    : {_fmt_bytes(args.l2_size)}, {args.l2_assoc}-way")
        print(f"│  L3    : {_fmt_bytes(args.l3_size)}, {args.l3_assoc}-way")
        print(f"└{'─' * 60}\n")
        for lvl in ("L1", "L2", "L3", "DRAM"):
            s = stats[lvl]
            hr = f"{s['hit_rate']*100:5.2f}%" if lvl != "DRAM" else "  n/a"
            print(f"  {lvl:<4}  accesses={s['accesses']:>7}  "
                  f"hits={s['hits']:>7}  misses={s['misses']:>7}  "
                  f"hit_rate={hr}")
        print()
        print(f"  avg latency = {summary['avg_latency_cycles']:.2f} cycles")
        print(f"  MPKI        = {summary['MPKI']:.2f}")

    if args.plot or args.save:
        from viz.visualizer import plot_multilevel_stats
        per_lvl = {k: v for k, v in stats.items() if k in ("L1", "L2", "L3")}
        fig = plot_multilevel_stats(["L1", "L2", "L3"], per_lvl,
                                    title=f"Hierarchy stats · {args.trace}")
        _handle_figure(fig, f"multilevel_{args.trace}",
                       args.save, show=args.plot)


def cmd_sweep_size(args: argparse.Namespace) -> None:
    """Sweep cache sizes for each policy."""
    trace = make_trace(args.trace, n=args.n)
    sizes, hr_by_pol = sweep_size(
        trace, args.sizes, policies=args.policies,
        assoc=args.assoc, block_size=args.block,
    )

    if args.json:
        out = {
            "trace": args.trace, "assoc": args.assoc, "block": args.block,
            "sizes": sizes,
            "hit_rates": hr_by_pol,
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"\n┌─ sweep-size · {args.trace} · {args.assoc}-way · "
              f"{args.block} B blocks {'─' * 20}")
        header = "  size".ljust(12) + "".join(p.ljust(12) for p in args.policies)
        print(header)
        for i, sz in enumerate(sizes):
            row = _fmt_bytes(sz).ljust(12)
            for p in args.policies:
                row += f"{hr_by_pol[p][i]*100:6.2f} %    "
            print("  " + row)
        print()

    if args.plot or args.save:
        from viz.visualizer import plot_hit_rate_vs_size
        fig = plot_hit_rate_vs_size(sizes, hr_by_pol,
                                    title=f"Hit Rate vs Size · {args.trace}")
        _handle_figure(fig, f"sweep_size_{args.trace}",
                       args.save, show=args.plot)


def cmd_sweep_assoc(args: argparse.Namespace) -> None:
    """Sweep associativity for each policy."""
    trace = make_trace(args.trace, n=args.n)
    assocs, hr_by_pol = sweep_assoc(
        trace, args.assocs, policies=args.policies,
        size_bytes=args.l1_size, block_size=args.block,
    )

    if args.json:
        out = {"trace": args.trace, "size": args.l1_size, "block": args.block,
               "assocs": assocs, "hit_rates": hr_by_pol}
        print(json.dumps(out, indent=2))
    else:
        print(f"\n┌─ sweep-assoc · {args.trace} · "
              f"{_fmt_bytes(args.l1_size)} · {args.block} B blocks {'─' * 14}")
        header = "  assoc".ljust(12) + "".join(p.ljust(12) for p in args.policies)
        print(header)
        for i, a in enumerate(assocs):
            row = (f"{a}-way" if a > 1 else "Direct").ljust(12)
            for p in args.policies:
                row += f"{hr_by_pol[p][i]*100:6.2f} %    "
            print("  " + row)
        print()

    if args.plot or args.save:
        from viz.visualizer import plot_hit_rate_vs_assoc
        fig = plot_hit_rate_vs_assoc(assocs, hr_by_pol,
                                     title=f"Hit Rate vs Assoc · {args.trace}")
        _handle_figure(fig, f"sweep_assoc_{args.trace}",
                       args.save, show=args.plot)


def cmd_compare_policies(args: argparse.Namespace) -> None:
    """Compare replacement policies at one cache config."""
    trace = make_trace(args.trace, n=args.n)
    policies, rates = compare_policies(
        trace, policies=args.policies,
        size_bytes=args.l1_size, assoc=args.assoc, block_size=args.block,
    )

    if args.json:
        out = {"trace": args.trace, "size": args.l1_size, "assoc": args.assoc,
               "block": args.block,
               "results": {p: r for p, r in zip(policies, rates)}}
        print(json.dumps(out, indent=2))
    else:
        print(f"\n┌─ compare-policies · {args.trace} · "
              f"{_fmt_bytes(args.l1_size)} · {args.assoc}-way {'─' * 12}")
        for p, r in zip(policies, rates):
            print(f"  {p:<8}  hit_rate = {r*100:6.2f} %")
        print()

    if args.plot or args.save:
        from viz.visualizer import plot_hit_rate_vs_policy
        cache_label = f"L1 ({_fmt_bytes(args.l1_size)}, {args.assoc}-way)"
        fig = plot_hit_rate_vs_policy(policies, rates,
                                      cache_label=cache_label,
                                      title=f"Policies · {args.trace}")
        _handle_figure(fig, f"compare_policies_{args.trace}",
                       args.save, show=args.plot)


def cmd_heatmap(args: argparse.Namespace) -> None:
    """2-D miss-rate heatmap: size × associativity."""
    trace = make_trace(args.trace, n=args.n)
    sizes, assocs, matrix = heatmap_size_x_assoc(
        trace, args.sizes, args.assocs,
        policy=args.policy, block_size=args.block,
    )

    if args.json:
        print(json.dumps({"trace": args.trace, "policy": args.policy,
                          "sizes": sizes, "assocs": assocs,
                          "miss_rate": matrix}, indent=2))
    else:
        print(f"\n┌─ heatmap · {args.trace} · policy={args.policy} {'─' * 30}")
        header = "  size".ljust(10) + "".join(
            ((f"{a}w" if a > 1 else "DM")).rjust(9) for a in assocs
        )
        print(header)
        for i, sz in enumerate(sizes):
            row = _fmt_bytes(sz).ljust(10)
            for v in matrix[i]:
                row += f"{v*100:7.2f}%"
            print("  " + row)
        print()

    if args.plot or args.save:
        from viz.visualizer import plot_miss_rate_heatmap
        fig = plot_miss_rate_heatmap(
            sizes, assocs, matrix,
            title=f"Miss Rate · {args.trace} · {args.policy}",
        )
        _handle_figure(fig, f"heatmap_{args.trace}_{args.policy}",
                       args.save, show=args.plot)


def cmd_3c(args: argparse.Namespace) -> None:
    """3C miss classification (Compulsory / Capacity / Conflict)."""
    results = {}
    labels, comp_l, cap_l, conf_l = [], [], [], []

    for tname in args.traces:
        addrs = make_trace(tname, n=args.n)
        r = classify_3c(addrs,
                        size_bytes=args.l1_size,
                        associativity=args.assoc,
                        block_size=args.block)
        results[tname] = r
        labels.append(tname)
        comp_l.append(r["compulsory"])
        cap_l.append(r["capacity"])
        conf_l.append(r["conflict"])

    if args.json:
        print(json.dumps({
            "cache": {"size": args.l1_size, "assoc": args.assoc,
                      "block": args.block},
            "results": results,
        }, indent=2))
    else:
        print(f"\n┌─ 3C classification · {_fmt_bytes(args.l1_size)} · "
              f"{args.assoc}-way · {args.block} B blocks {'─' * 8}")
        print("  trace".ljust(14) + "Compulsory".rjust(12)
              + "Capacity".rjust(12) + "Conflict".rjust(12) + "Total".rjust(10))
        for t in args.traces:
            r = results[t]
            tot = r["compulsory"] + r["capacity"] + r["conflict"]
            print("  " + t.ljust(12)
                  + f"{r['compulsory']:>12}"
                  + f"{r['capacity']:>12}"
                  + f"{r['conflict']:>12}"
                  + f"{tot:>10}")
        print()

    if args.plot or args.save:
        from viz.visualizer import plot_3c_breakdown
        fig = plot_3c_breakdown(labels, comp_l, cap_l, conf_l,
                                title=f"3C · {_fmt_bytes(args.l1_size)} · "
                                      f"{args.assoc}-way")
        _handle_figure(fig, "three_c_breakdown",
                       args.save, show=args.plot)


def cmd_demo(args: argparse.Namespace) -> None:
    """Run the full visualization demo."""
    # delegate to viz.demo for the canonical demo
    import runpy
    runpy.run_module("viz.demo", run_name="__main__")


# ────────────────────────────────────────────────────────────────────────
# argparse setup
# ────────────────────────────────────────────────────────────────────────

_TRACES_HELP = "one of: " + ", ".join(list_traces())


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--n", type=int, default=4000,
                   help="trace length (default 4000)")
    p.add_argument("--block", type=int, default=64,
                   help="block size in bytes (default 64)")
    p.add_argument("--plot", action="store_true",
                   help="open a matplotlib window")
    p.add_argument("--save", metavar="DIR",
                   help="save figure as PNG into this directory")
    p.add_argument("--json", action="store_true",
                   help="print results as JSON (machine-readable)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python main.py",
        description="Cache Hierarchy Simulator — CLI (Person #3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run `python main.py <cmd> --help` for command-specific options.",
    )
    p.add_argument("--quiet", action="store_true", help="suppress banner")
    sub = p.add_subparsers(dest="cmd", required=False)
    # single ------------------------------------------------------------
    s = sub.add_parser("single", help="one trace · one cache · print stats")
    _add_common(s)
    s.add_argument("--l1-size", type=_parse_size, default=_parse_size("32k"))
    s.add_argument("--assoc",   type=int, default=4)
    s.add_argument("--policy",  default="LRU", choices=["LRU", "Clock", "RRIP"])
    s.add_argument("--trace",   default="random", help=_TRACES_HELP)
    s.set_defaults(func=cmd_single)

    # multilevel --------------------------------------------------------
    m = sub.add_parser("multilevel", help="one trace · L1→L2→L3 hierarchy")
    _add_common(m)
    m.add_argument("--l1-size", type=_parse_size, default=_parse_size("32k"))
    m.add_argument("--l2-size", type=_parse_size, default=_parse_size("256k"))
    m.add_argument("--l3-size", type=_parse_size, default=_parse_size("8m"))
    m.add_argument("--l1-assoc", type=int, default=4)
    m.add_argument("--l2-assoc", type=int, default=8)
    m.add_argument("--l3-assoc", type=int, default=16)
    m.add_argument("--policy",   default="LRU",
                   choices=["LRU", "Clock", "RRIP"])
    m.add_argument("--trace",    default="random", help=_TRACES_HELP)
    m.set_defaults(func=cmd_multilevel)

    # sweep-size --------------------------------------------------------
    ss = sub.add_parser("sweep-size",
                        help="sweep cache size for each policy")
    _add_common(ss)
    ss.add_argument("--sizes",
                    type=_parse_size_list,
                    default=_parse_size_list("4k,8k,16k,32k,64k,128k,256k,512k"))
    ss.add_argument("--assoc",    type=int, default=4)
    ss.add_argument("--policies", type=_parse_str_list,
                    default=["LRU", "Clock", "RRIP"])
    ss.add_argument("--trace",    default="random", help=_TRACES_HELP)
    ss.set_defaults(func=cmd_sweep_size)

    # sweep-assoc -------------------------------------------------------
    sa = sub.add_parser("sweep-assoc",
                        help="sweep associativity for each policy")
    _add_common(sa)
    sa.add_argument("--assocs",   type=_parse_int_list, default=[1, 2, 4, 8, 16])
    sa.add_argument("--l1-size",  type=_parse_size, default=_parse_size("32k"))
    sa.add_argument("--policies", type=_parse_str_list,
                    default=["LRU", "Clock", "RRIP"])
    sa.add_argument("--trace",    default="random", help=_TRACES_HELP)
    sa.set_defaults(func=cmd_sweep_assoc)

    # compare-policies --------------------------------------------------
    cp = sub.add_parser("compare-policies",
                        help="compare LRU / Clock / RRIP at one config")
    _add_common(cp)
    cp.add_argument("--l1-size",  type=_parse_size, default=_parse_size("32k"))
    cp.add_argument("--assoc",    type=int, default=4)
    cp.add_argument("--policies", type=_parse_str_list,
                    default=["LRU", "Clock", "RRIP"])
    cp.add_argument("--trace",    default="random", help=_TRACES_HELP)
    cp.set_defaults(func=cmd_compare_policies)

    # heatmap -----------------------------------------------------------
    hm = sub.add_parser("heatmap", help="2-D heatmap: size × assoc")
    _add_common(hm)
    hm.add_argument("--sizes",  type=_parse_size_list,
                    default=_parse_size_list("4k,8k,16k,32k,64k"))
    hm.add_argument("--assocs", type=_parse_int_list, default=[1, 2, 4, 8])
    hm.add_argument("--policy", default="LRU", choices=["LRU", "Clock", "RRIP"])
    hm.add_argument("--trace",  default="random", help=_TRACES_HELP)
    hm.set_defaults(func=cmd_heatmap)

    # 3c ----------------------------------------------------------------
    c = sub.add_parser("3c", help="3C miss classification")
    _add_common(c)
    c.add_argument("--traces", type=_parse_str_list,
                   default=["sequential", "random", "matrix", "thrash"])
    c.add_argument("--l1-size", type=_parse_size, default=_parse_size("32k"))
    c.add_argument("--assoc",   type=int, default=4)
    c.set_defaults(func=cmd_3c)

    # demo --------------------------------------------------------------
    d = sub.add_parser("demo", help="run the full viz demo (6 plots)")
    d.set_defaults(func=cmd_demo)

    return p


# ────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────

def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --quiet можно поставить и перед, и после subcommand
    quiet = getattr(args, "quiet", False)

    if not getattr(args, "cmd", None):
        # No subcommand → run a friendly default tour
        _print_banner(False)
        print("No subcommand given — running the default tour.")
        print("Try `python main.py --help` for the full list of commands.\n")

        # Reasonable defaults: a multilevel run on a random trace + a 3C demo.
        ns = argparse.Namespace(
            n=4000, block=64, plot=False, save=None, json=False,
            trace="random",
            l1_size=32 * 1024, l2_size=256 * 1024, l3_size=8 * 1024 * 1024,
            l1_assoc=4, l2_assoc=8, l3_assoc=16,
            policy="LRU",
        )
        cmd_multilevel(ns)

        print("\nNow a quick policy comparison on a thrash trace:")
        ns2 = argparse.Namespace(
            n=4000, block=64, plot=False, save=None, json=False,
            trace="thrash", l1_size=32 * 1024, assoc=4,
            policies=["LRU", "Clock", "RRIP"],
        )
        cmd_compare_policies(ns2)

        print("\nAnd a 3C breakdown across all built-in traces:")
        ns3 = argparse.Namespace(
            n=4000, block=64, plot=False, save=None, json=False,
            traces=["sequential", "random", "matrix", "thrash"],
            l1_size=32 * 1024, assoc=4,
        )
        cmd_3c(ns3)

        print(
            "\nTip:\n"
            "  python main.py multilevel --trace matrix --plot\n"
            "  python main.py sweep-size --sizes 4k,8k,16k,32k,64k,128k --plot\n"
            "  python main.py 3c --plot\n"
        )
        return 0

    _print_banner(getattr(args, "quiet", False))
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
