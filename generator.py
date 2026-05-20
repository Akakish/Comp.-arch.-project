"""
traces/generator.py
-------------------
Генерирует синтетические трассы обращений к памяти.

Поддерживаемые паттерны:
  sequential  — линейный проход по массиву
  random      — случайные адреса по всему адресному пространству
  matrix      — обход матрицы (row-major + col-major для thrash-демо)
  thrash      — рабочий набор, который чуть больше размера кэша → непрерывный thrashing

Каждая функция возвращает list[int] — список адресов (в байтах).
"""

import random as _random
import struct as _struct
from pathlib import Path


# ───────────────────────────── helpers ──────────────────────────────

def _align(addr: int, block_size: int) -> int:
    """Выровнять адрес по границе блока."""
    return (addr // block_size) * block_size


# ───────────────────────────── generators ───────────────────────────

def sequential(
    num_accesses: int = 4096,
    start_addr: int = 0x1000,
    stride: int = 4,
) -> list[int]:
    """
    Линейный проход: start, start+stride, start+2*stride, …

    Параметры
    ---------
    num_accesses : сколько обращений сгенерировать
    start_addr   : стартовый адрес
    stride       : шаг в байтах (4 = int, 8 = double)
    """
    return [start_addr + i * stride for i in range(num_accesses)]


def random_trace(
    num_accesses: int = 4096,
    addr_space: int = 1 << 20,   # 1 MB по умолчанию
    seed: int | None = 42,
    block_size: int = 64,
) -> list[int]:
    """
    Случайные обращения по всему адресному пространству addr_space.
    Адреса выровнены по block_size (имитируем гранулярность кэш-линии).

    Параметры
    ---------
    num_accesses : количество обращений
    addr_space   : размер адресного пространства в байтах
    seed         : seed для воспроизводимости (None — случайный)
    block_size   : выравнивание адресов
    """
    rng = _random.Random(seed)
    num_blocks = addr_space // block_size
    return [rng.randint(0, num_blocks - 1) * block_size for _ in range(num_accesses)]


def matrix(
    rows: int = 64,
    cols: int = 64,
    elem_size: int = 4,
    order: str = "row",
    base_addr: int = 0x2000,
) -> list[int]:
    """
    Обход двумерной матрицы.

    Параметры
    ---------
    rows, cols  : размер матрицы
    elem_size   : размер элемента в байтах
    order       : "row" (row-major, cache-friendly)
                  "col" (column-major, cache-unfriendly — много промахов)
    base_addr   : базовый адрес матрицы
    """
    if order == "row":
        return [
            base_addr + (r * cols + c) * elem_size
            for r in range(rows)
            for c in range(cols)
        ]
    elif order == "col":
        return [
            base_addr + (r * cols + c) * elem_size
            for c in range(cols)
            for r in range(rows)
        ]
    else:
        raise ValueError(f"order должен быть 'row' или 'col', получено: {order!r}")


def thrash(
    cache_size_bytes: int = 32 * 1024,
    overfill_factor: float = 1.5,
    num_passes: int = 4,
    block_size: int = 64,
    base_addr: int = 0x0,
) -> list[int]:
    """
    Рабочий набор = overfill_factor * cache_size_bytes.
    Несколько проходов по этому набору вызывают постоянные capacity-miss.

    Параметры
    ---------
    cache_size_bytes : размер L1-кэша в байтах
    overfill_factor  : во сколько раз рабочий набор превышает кэш
    num_passes       : сколько раз пройтись по набору
    block_size       : размер кэш-линии
    base_addr        : базовый адрес
    """
    working_set_bytes = int(cache_size_bytes * overfill_factor)
    num_blocks = working_set_bytes // block_size
    addrs = []
    for _ in range(num_passes):
        for i in range(num_blocks):
            addrs.append(base_addr + i * block_size)
    return addrs


# ───────────────────────────── file I/O ─────────────────────────────

def save_trace(addrs: list[int], path: str | Path) -> None:
    """Сохранить трассу в бинарный файл (little-endian uint64)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        for addr in addrs:
            f.write(_struct.pack("<Q", addr))


def load_trace(path: str | Path) -> list[int]:
    """Загрузить трассу из бинарного файла."""
    path = Path(path)
    data = path.read_bytes()
    count = len(data) // 8
    return list(_struct.unpack_from(f"<{count}Q", data))


def save_trace_text(addrs: list[int], path: str | Path) -> None:
    """Сохранить трассу как текстовый файл (один адрес на строку, hex)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for addr in addrs:
            f.write(f"0x{addr:016x}\n")


def load_trace_text(path: str | Path) -> list[int]:
    """Загрузить трассу из текстового файла."""
    addrs = []
    with open(Path(path)) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                addrs.append(int(line, 16))
    return addrs


# ───────────────────────────── convenience ──────────────────────────

GENERATORS = {
    "sequential": sequential,
    "random":     random_trace,
    "matrix":     matrix,
    "thrash":     thrash,
}


def generate(name: str, **kwargs) -> list[int]:
    """
    Генерировать трассу по имени паттерна.

    Пример:
        addrs = generate("sequential", num_accesses=1024, stride=8)
    """
    if name not in GENERATORS:
        raise ValueError(f"Неизвестный паттерн: {name!r}. Доступны: {list(GENERATORS)}")
    return GENERATORS[name](**kwargs)
