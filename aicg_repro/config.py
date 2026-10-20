"""配置加载、校验、快照与随机种子策略。

所有实验参数集中在 JSON 配置文件中，代码只读取配置、不硬编码实验参数。
配置快照（合并默认值后的完整字典）会随每次运行写入 manifest 与实验目录，
保证实验可追溯、可复现。
"""

from __future__ import annotations

import copy
import json
import random
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from .errors import ConfigError

# --------------------------------------------------------------------------- #
# 默认值（用户配置为增量覆盖）
# --------------------------------------------------------------------------- #
DEFAULTS: Dict[str, Any] = {
    "experiment": {
        "name": "AIGC 最终输出可复现性实验",
        "description": "",
        "prompt": "default prompt",
        "tags": [],
    },
    "num_runs": 5,
    "num_pairs": None,
    "replicates_per_pair": 2,
    "max_iterations_per_run": 20,
    "random": {"strategy": "fixed", "master_seed": 20240601},
    "stop_conditions": {
        "quality_threshold": None,
        "no_improvement_rounds": None,
    },
    "rollback": {
        "enabled": True,
        "max_consecutive_rollbacks": 5,
        "tolerance": 0.0,
    },
    "generator": {"type": "mock", "mock": {"image_size": [256, 256], "watermark": "MOCK_ONLY"}},
    "evaluator": {"type": "mock"},
    "comparison": {"metrics": ["sha256", "pixel_consistency"], "reserved": {"ssim": None, "lpips": None}},
    "paths": {"output_root": "runs", "reports_dir": "reports", "logs_dir": "logs"},
    "error_handling": {
        "max_retries": 3,
        "retry_backoff_seconds": 0.05,
        "checkpoint_enabled": True,
        "abort_on_failure": False,
    },
}

_SEED_STRATEGIES = ("fixed", "run_index", "random")


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并配置：override 中的键覆盖 base，列表与标量整体替换。"""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_config(path: Optional[Path | str] = None) -> Dict[str, Any]:
    """加载 JSON 配置并合并默认值，返回完整配置字典。"""
    user_cfg: Dict[str, Any] = {}
    if path is not None:
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"配置文件不存在: {p}")
        try:
            user_cfg = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"配置文件 JSON 解析失败: {p} ({exc})") from exc
        if not isinstance(user_cfg, dict):
            raise ConfigError(f"配置文件顶层必须是 JSON 对象: {p}")
    cfg = _deep_merge(DEFAULTS, user_cfg)
    validate_config(cfg)
    return cfg


def validate_config(cfg: Dict[str, Any]) -> None:
    """校验合并后的配置，任何不合法都抛 ConfigError。"""
    if not isinstance(cfg.get("num_runs"), int) or cfg["num_runs"] < 1:
        raise ConfigError("num_runs 必须是 >= 1 的整数")
    if cfg.get("num_pairs") is not None and (
        not isinstance(cfg["num_pairs"], int) or cfg["num_pairs"] < 1
    ):
        raise ConfigError("num_pairs 必须是 >= 1 的整数（或省略以使用 num_runs）")
    if not isinstance(cfg.get("replicates_per_pair"), int) or cfg["replicates_per_pair"] < 1:
        raise ConfigError("replicates_per_pair 必须是 >= 1 的整数")
    if not isinstance(cfg.get("max_iterations_per_run"), int) or cfg["max_iterations_per_run"] < 1:
        raise ConfigError("max_iterations_per_run 必须是 >= 1 的整数")
    strategy = cfg["random"]["strategy"]
    if strategy not in _SEED_STRATEGIES:
        raise ConfigError(f"random.strategy 必须是 {_SEED_STRATEGIES} 之一，得到: {strategy!r}")
    if not isinstance(cfg["random"]["master_seed"], int):
        raise ConfigError("random.master_seed 必须是整数")
    if cfg["rollback"]["enabled"] and not isinstance(cfg["rollback"]["max_consecutive_rollbacks"], int):
        raise ConfigError("rollback.max_consecutive_rollbacks 必须是整数")
    gen_type = cfg["generator"]["type"]
    if gen_type not in ("mock", "comfyui"):
        raise ConfigError(f"generator.type 仅支持 'mock' / 'comfyui'，得到: {gen_type!r}")
    ev_type = cfg["evaluator"]["type"]
    if ev_type not in ("mock", "clip"):
        raise ConfigError(f"evaluator.type 仅支持 'mock' / 'clip'，得到: {ev_type!r}")
    metrics = cfg["comparison"]["metrics"]
    known = {"sha256", "pixel_consistency", "ssim", "lpips"}
    if not isinstance(metrics, list) or not all(m in known for m in metrics):
        raise ConfigError(f"comparison.metrics 仅支持 {sorted(known)} 子集，得到: {metrics!r}")


def config_snapshot(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """返回可序列化、键有序的配置快照（深拷贝）。"""
    return json.loads(json.dumps(cfg, ensure_ascii=False, sort_keys=True, default=str))


def resolve_seed(cfg: Dict[str, Any], run_index: int) -> int:
    """按策略解析某次运行的随机种子。

    - fixed:     所有运行使用同一 master_seed（用于验证确定性）；
    - run_index: seed = master_seed + run_index（用于观察可变性）；
    - random:    每次使用密码学随机数（记录在 manifest 中，保证可追溯）。
    """
    strategy = cfg["random"]["strategy"]
    master = cfg["random"]["master_seed"]
    if strategy == "fixed":
        return master
    if strategy == "run_index":
        return master + run_index
    if strategy == "random":
        return secrets.randbelow(2**31 - 1)
    raise ConfigError(f"未知种子策略: {strategy!r}")


def new_experiment_id() -> str:
    """生成不会与已有结果冲突的实验 ID。"""
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"exp_{stamp}_{secrets.token_hex(4)}"
