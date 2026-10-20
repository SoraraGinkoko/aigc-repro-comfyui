#!/usr/bin/env python3
"""预先生成并保存种子簿（供「同一创作者独立重复创作」实验）。

用法（在项目根目录或任意目录均可）：

    python scripts\\generate_seed_book.py [num_pairs] [length] [master_seed]

默认：10 对（20 条序列）、每条 20 个种子、master_seed=20240601。
生成后写入 config/seed_book.json；所有序列之间互不重复、无平移重叠。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aicg_repro.seeds import generate_seed_book, save_seed_book

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    num_pairs = int(argv[0]) if len(argv) > 0 else 10
    length = int(argv[1]) if len(argv) > 1 else 20
    master_seed = int(argv[2]) if len(argv) > 2 else 20240601

    num_sequences = num_pairs * 2
    book = generate_seed_book(num_sequences, length, master_seed)

    # 校验互不重复
    flat = [s for seq in book for s in seq]
    assert len(flat) == len(set(flat)), "种子簿出现重复值（不应发生）"

    out = PROJECT_ROOT / "config" / "seed_book.json"
    save_seed_book(out, book)
    print(f"已生成种子簿: {out}")
    print(f"  序列数 = {num_sequences}（{num_pairs} 对 × 2）| 每条长度 = {length} | master_seed = {master_seed}")
    print(f"  全部 {len(flat)} 个种子互不重复")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
