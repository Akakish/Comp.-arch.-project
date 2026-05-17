# Cache Hierarchy Simulator — Core Module

> **Author:** Person #1  
> **Part:** Core simulator engine  
> **Files:** `core/block.py`, `core/policy.py`, `core/cache_level.py`, `core/hierarchy.py`

---

## What this module does

The `core/` package is the engine of the entire simulator.  
All other parts (trace generator, CLI, visualizer) import from here.

### Files

| File | Responsibility |
|---|---|
| `block.py` | `CacheBlock` — a single cache line with tag, dirty bit, RRPV, ref bit |
| `policy.py` | Replacement policies: **LRU**, **Clock**, **RRIP** + factory function |
| `cache_level.py` | `CacheLevel` — one configurable cache level with full hit/miss/evict logic |
| `hierarchy.py` | `CacheHierarchy` — wires L1→L2→L3→DRAM, tracks latency and MPKI |

---

## Address breakdown

```
Physical address (32-bit):
┌──────────────────┬────────────────┬───────────────┐
│       tag        │   set_index    │ block_offset  │
│  (remaining bits)│  log2(sets) b  │  log2(block)b │
└──────────────────┴────────────────┴───────────────┘
```

Example — 32 KB, 4-way, 64 B blocks:
- block_offset = 6 bits (64 = 2⁶)
- sets = 32768 / (4 × 64) = 128 → set_index = 7 bits
- tag = 32 − 6 − 7 = 19 bits

---

## Replacement policies

### LRU (Least Recently Used)
Tracks access order with `OrderedDict`. On hit → move to MRU end. On miss → evict front (LRU). Exact, O(1) per access.

### Clock (Second Chance)
Approximates LRU with a single reference bit per block and a sweeping hand. Cheaper hardware than LRU, nearly as effective.

### RRIP (Re-Reference Interval Prediction)
Each block has a 2-bit RRPV counter (0–3). Inserted with RRPV=2 (distant). Hit → RRPV=0 (near). Evict → find RRPV=3 (if none, increment all). Protects frequently-used blocks better than LRU on mixed workloads.

---

## Quick usage

```python
from core import CacheHierarchy

# Default: L1=32KB/4-way, L2=256KB/8-way, L3=8MB/16-way, all LRU
h = CacheHierarchy()

result = h.access(0xDEADBEEF)
print(result.hit_level)      # "DRAM" (cold miss)

result = h.access(0xDEADBEEF)
print(result.hit_level)      # "L1" (warm hit)

print(h.summary())
```

Custom config:

```python
h = CacheHierarchy(
    l1_size=16*1024, l1_assoc=2, l1_block=64, l1_policy="RRIP",
    l2_size=256*1024, l2_assoc=8, l2_block=64, l2_policy="Clock",
    l3_size=8*1024*1024, l3_assoc=16, l3_block=64, l3_policy="LRU",
)
```

---

## Running tests

```bash
pip install pytest
pytest tests/test_core.py -v
```

Expected output: **all tests pass**.

---

## Interface for teammates

Other team members should import only from `core/`:

```python
from core import CacheHierarchy, AccessResult   # Person #2 (traces)
from core import CacheHierarchy                 # Person #3 (CLI)
from core import CacheHierarchy                 # Person #4 (viz)
```

`AccessResult` fields available after each `h.access(addr)`:
- `.hit_level` — `"L1"`, `"L2"`, `"L3"`, or `"DRAM"`
- `.latency_cycles` — integer
- `.is_compulsory`, `.is_capacity`, `.is_conflict` — filled by Person #2
