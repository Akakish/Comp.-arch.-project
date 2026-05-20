"""
traces/demo.py
--------------
Демонстрация: генерируем 4 трассы, запускаем 3C-анализ, выводим результаты.
Запуск из корня проекта:
    python -m traces.demo
"""

from traces.generator import sequential, random_trace, matrix, thrash
from traces.analysis import classify_3c, print_3c_report

# ─── параметры кэша ───────────────────────────────────────────────
CACHE_SIZE      = 32 * 1024   # 32 KB
ASSOCIATIVITY   = 4
BLOCK_SIZE      = 64          # bytes

print("Cache config:")
print(f"  Size         : {CACHE_SIZE // 1024} KB")
print(f"  Associativity: {ASSOCIATIVITY}-way")
print(f"  Block size   : {BLOCK_SIZE} B")
print()

# ─── 1. Sequential ────────────────────────────────────────────────
addrs = sequential(num_accesses=8192, stride=4)
result = classify_3c(addrs, CACHE_SIZE, ASSOCIATIVITY, BLOCK_SIZE)
print_3c_report(result, total_accesses=len(addrs), label="Sequential")

# ─── 2. Random ────────────────────────────────────────────────────
addrs = random_trace(num_accesses=8192, addr_space=256 * 1024)
result = classify_3c(addrs, CACHE_SIZE, ASSOCIATIVITY, BLOCK_SIZE)
print_3c_report(result, total_accesses=len(addrs), label="Random")

# ─── 3. Matrix row-major (friendly) ───────────────────────────────
addrs = matrix(rows=64, cols=64, order="row")
result = classify_3c(addrs, CACHE_SIZE, ASSOCIATIVITY, BLOCK_SIZE)
print_3c_report(result, total_accesses=len(addrs), label="Matrix row-major")

# ─── 4. Matrix col-major (unfriendly) ─────────────────────────────
addrs = matrix(rows=64, cols=64, order="col")
result = classify_3c(addrs, CACHE_SIZE, ASSOCIATIVITY, BLOCK_SIZE)
print_3c_report(result, total_accesses=len(addrs), label="Matrix col-major")

# ─── 5. Thrash ────────────────────────────────────────────────────
addrs = thrash(cache_size_bytes=CACHE_SIZE, overfill_factor=1.5, num_passes=4)
result = classify_3c(addrs, CACHE_SIZE, ASSOCIATIVITY, BLOCK_SIZE)
print_3c_report(result, total_accesses=len(addrs), label="Thrash (1.5× cache)")
