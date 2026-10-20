"""种子序列与种子簿模块。

- 单条序列：``generate/load/save_seed_sequence``（兼容旧配置与测试）。
- **种子簿**：``generate/load/save_seed_book`` —— 供「同一创作者独立重复创作」实验使用。
  每条创作一条种子序列；所有序列之间**互不重复**（无交叉、无平移重叠），
  由 ``master_seed`` 确定性生成，正式实验前落盘、可审计，绝不事后挑选。
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

from .errors import ConfigError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_config_path(path: str | None) -> Path | None:
    """相对路径优先按当前目录解析；找不到则回退到项目根目录。"""
    if path is None:
        return None
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p
    return _PROJECT_ROOT / path


# --------------------------------------------------------------------------- #
# 单条种子序列（兼容旧配置）
# --------------------------------------------------------------------------- #


def generate_seed_sequence(length: int, base_seed: int = 0) -> List[int]:
    """用确定性 LCG 生成一个种子序列（仅用于首次生成，之后固定保存）。"""
    sequence: List[int] = []
    x = base_seed
    for _ in range(length):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        sequence.append(x)
    return sequence


def save_seed_sequence(path: str | Path, sequence: List[int]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"length": len(sequence), "sequence": sequence}, indent=2),
        encoding="utf-8",
    )
    return p


def load_seed_sequence(path: str | Path) -> List[int]:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"种子序列文件不存在: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"种子序列文件 JSON 解析失败: {p}") from exc
    seq = data.get("sequence")
    if not isinstance(seq, list) or not all(isinstance(s, int) for s in seq):
        raise ConfigError(f"种子序列格式非法（需为整数数组）: {p}")
    return seq


# --------------------------------------------------------------------------- #
# 种子簿（每条创作一条序列）
# --------------------------------------------------------------------------- #


def generate_seed_book(num_sequences: int, length: int, master_seed: int) -> List[List[int]]:
    """确定性生成 ``num_sequences`` 条、每条 ``length`` 个的种子序列。

    用 ``random.Random(master_seed).sample`` 一次抽取 ``num_sequences*length`` 个
    互不相同的整数，再切成若干条 —— 因此**任意两条序列之间无重复、无平移重叠**。
    """
    if num_sequences < 1 or length < 1:
        raise ConfigError("种子簿的序列数与长度都必须 >= 1")
    rng = random.Random(f"aicg-seedbook:{master_seed}")
    total = num_sequences * length
    pool = rng.sample(range(1, 2**31 - 1), total)
    return [pool[i * length : (i + 1) * length] for i in range(num_sequences)]


def save_seed_book(path: str | Path, sequences: List[List[int]]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "num_sequences": len(sequences),
        "length": len(sequences[0]) if sequences else 0,
        "master_seed_note": "由 master_seed 确定性生成；正式实验前落盘，绝不事后挑选。",
        "sequences": sequences,
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def load_seed_book(path: str | Path) -> List[List[int]]:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"种子簿文件不存在: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"种子簿 JSON 解析失败: {p}") from exc
    seqs = data.get("sequences")
    if not isinstance(seqs, list) or not seqs:
        raise ConfigError(f"种子簿格式非法（需为二维整数数组）: {p}")
    for s in seqs:
        if not isinstance(s, list) or not all(isinstance(x, int) for x in s):
            raise ConfigError(f"种子簿某条序列格式非法: {p}")
    lengths = {len(s) for s in seqs}
    if len(lengths) != 1:
        raise ConfigError(f"种子簿各序列长度不一致: {p}")
    return seqs
