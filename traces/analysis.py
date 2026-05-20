"""
traces/analysis.py
------------------
3C-классификация промахов кэша.

Три вида промахов:
  Compulsory (cold)  — первое обращение к блоку (unavoidable)
  Capacity           — промах из-за недостаточного размера кэша
                       (пропал бы даже в fully-associative кэше того же размера)
  Conflict           — промах из-за ограниченной ассоциативности
                       (не пропал бы в fully-associative кэше)

Алгоритм
--------
1. Compulsory: отслеживаем множество уже виденных блоков.
   Первое обращение → compulsory miss.

2. Capacity: симулируем идеальный fully-associative LRU кэш размером size_bytes.
   Промах в FA = capacity miss (уже не compulsory).

3. Conflict: симулируем реальный set-associative LRU кэш.
   Промах в SA, которого не было в FA = conflict miss.

Интерфейс
---------
classify_3c(addrs, size_bytes, associativity, block_size) -> dict
"""

from __future__ import annotations
from collections import OrderedDict


# ───────────────────────────── LRU симулятор ───────────────────────

class _LRUCache:
    """
    Простой LRU-кэш на OrderedDict.
    capacity — максимальное число блоков (строк) в кэше.
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity должна быть > 0")
        self.capacity = capacity
        self._store: OrderedDict[int, None] = OrderedDict()

    def access(self, block_id: int) -> bool:
        """
        Обратиться к block_id.
        Возвращает True если HIT, False если MISS.
        """
        if block_id in self._store:
            self._store.move_to_end(block_id)
            return True
        # MISS — загрузить блок
        if len(self._store) >= self.capacity:
            self._store.popitem(last=False)   # вытеснить LRU
        self._store[block_id] = None
        return False


class _SetAssocLRUCache:
    """
    Set-associative LRU кэш.
    Число сетов = (size_bytes // block_size) // associativity
    """

    def __init__(self, size_bytes: int, associativity: int, block_size: int) -> None:
        self.block_size = block_size
        total_blocks = size_bytes // block_size
        if total_blocks <= 0:
            raise ValueError("size_bytes слишком мал")
        self.num_sets = max(1, total_blocks // associativity)
        self.ways = associativity
        # один LRU на каждый сет
        self._sets: list[_LRUCache] = [
            _LRUCache(self.ways) for _ in range(self.num_sets)
        ]

    def access(self, addr: int) -> bool:
        block_id = addr // self.block_size
        set_idx = block_id % self.num_sets
        tag = block_id // self.num_sets
        return self._sets[set_idx].access(tag)


class _FullyAssocLRUCache:
    """
    Fully-associative LRU кэш (один сет на весь кэш).
    """

    def __init__(self, size_bytes: int, block_size: int) -> None:
        self.block_size = block_size
        total_blocks = max(1, size_bytes // block_size)
        self._lru = _LRUCache(total_blocks)

    def access(self, addr: int) -> bool:
        block_id = addr // self.block_size
        return self._lru.access(block_id)


# ───────────────────────────── основной API ─────────────────────────

def classify_3c(
    addrs: list[int],
    size_bytes: int,
    associativity: int,
    block_size: int,
) -> dict:
    """
    Классифицировать промахи по типам Compulsory / Capacity / Conflict.

    Параметры
    ----------
    addrs         : список адресов из трассы (каждый int — байтовый адрес)
    size_bytes    : размер кэша в байтах (напр. 32 * 1024 для 32 KB)
    associativity : ассоциативность (напр. 4 для 4-way)
    block_size    : размер кэш-линии в байтах (напр. 64)

    Возвращает
    ----------
    dict со следующими ключами:
        "compulsory" : int  — число cold-промахов
        "capacity"   : int  — число capacity-промахов
        "conflict"   : int  — число conflict-промахов

    Сумма compulsory + capacity + conflict == полное число промахов
    в симулируемом SA-кэше.
    """
    seen_blocks: set[int] = set()
    fa_cache = _FullyAssocLRUCache(size_bytes, block_size)
    sa_cache = _SetAssocLRUCache(size_bytes, associativity, block_size)

    compulsory = 0
    capacity   = 0
    conflict   = 0

    for addr in addrs:
        block_id = addr // block_size

        hit_sa = sa_cache.access(addr)
        hit_fa = fa_cache.access(addr)
        is_new = block_id not in seen_blocks

        if is_new:
            seen_blocks.add(block_id)

        if hit_sa:
            # SA hit → нет промаха вообще
            continue

        # SA miss — определяем тип
        if is_new:
            compulsory += 1
        elif not hit_fa:
            # FA тоже промахнулся → capacity
            capacity += 1
        else:
            # FA попал, SA промахнулся → conflict
            conflict += 1

    return {
        "compulsory": compulsory,
        "capacity":   capacity,
        "conflict":   conflict,
    }


# ───────────────────────────── утилиты ──────────────────────────────

def total_misses(result: dict) -> int:
    """Суммарное число промахов из результата classify_3c."""
    return result["compulsory"] + result["capacity"] + result["conflict"]


def miss_percentages(result: dict) -> dict[str, float]:
    """
    Вернуть процентное соотношение каждого типа промахов.
    Если промахов нет — вернуть нули.
    """
    total = total_misses(result)
    if total == 0:
        return {"compulsory": 0.0, "capacity": 0.0, "conflict": 0.0}
    return {k: 100.0 * v / total for k, v in result.items()}


def print_3c_report(
    result: dict,
    total_accesses: int | None = None,
    label: str = "",
) -> None:
    """Вывести красивый текстовый отчёт о 3C-анализе."""
    header = f"=== 3C Analysis{': ' + label if label else ''} ==="
    print(header)

    total = total_misses(result)
    pct = miss_percentages(result)

    print(f"  Compulsory (cold) : {result['compulsory']:>8,}  ({pct['compulsory']:5.1f}%)")
    print(f"  Capacity          : {result['capacity']:>8,}  ({pct['capacity']:5.1f}%)")
    print(f"  Conflict          : {result['conflict']:>8,}  ({pct['conflict']:5.1f}%)")
    print(f"  ─────────────────────────────────────")
    print(f"  Total misses      : {total:>8,}")

    if total_accesses is not None and total_accesses > 0:
        miss_rate = 100.0 * total / total_accesses
        hit_rate  = 100.0 - miss_rate
        print(f"  Hit rate          : {hit_rate:>7.2f}%")
        print(f"  Miss rate         : {miss_rate:>7.2f}%")
    print()
