"""运行状态与状态重置。

每次运行前调用 :meth:`StateManager.fresh` 创建全新、隔离的 :class:`RunState`：

- 独立的工作目录（不同运行之间不共享、不残留）；
- 独立的随机数发生器；
- 不持有任何跨运行的可变模块级状态。

这从机制上保证「上一轮实验的工作状态不会意外进入下一次实验」。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .errors import ReproError


@dataclass
class RoundRecord:
    """一轮操作的审计记录。"""

    round: int
    action: str  # generate | accept | rollback | accept_regression
    score: Optional[float]
    note: str = ""
    sha256_prefix: str = ""
    seed: Optional[int] = None  # 本轮实际使用的种子（来自预设序列）
    rollback_count: int = 0  # 本轮决策后的连续回退（拒绝）次数
    no_improvement_count: int = 0  # 本轮决策后的连续未提升次数


@dataclass
class RunState:
    """单次运行的全部可变状态，创建后不再被其他运行共享。"""

    run_id: str
    run_index: int
    seed: int
    work_dir: Path
    prompt: str
    rng: random.Random
    pair_id: int = 1
    replicate_id: int = 1
    seed_sequence: Optional[List[int]] = None  # 本次创作实际使用的种子序列
    history: List[RoundRecord] = field(default_factory=list)
    best_image: Any = None
    best_score: Optional[float] = None
    current_image: Any = None
    current_score: Optional[float] = None
    rollback_count: int = 0
    no_improvement_count: int = 0
    stop_reason: Optional[str] = None
    rounds_actual: int = 0

    def add_record(self, rec: RoundRecord) -> None:
        self.history.append(rec)


class StateManager:
    """为每次运行创建隔离的新状态，并阻止跨运行状态泄漏。"""

    def __init__(self, experiment_dir: Path, config: Dict[str, Any]):
        self.experiment_dir = Path(experiment_dir)
        self.config = config

    @property
    def runs_root(self) -> Path:
        return self.experiment_dir / "runs"

    def run_dir(self, run_index: int) -> Path:
        return self.runs_root / f"run_{run_index:03d}"

    def fresh(self, run_index: int, seed: int, pair_id: int = 1, replicate_id: int = 1) -> RunState:
        """创建全新隔离状态。

        若目标目录已存在则拒绝创建（宁可报错也不静默复用上一轮残留）。
        """
        work_dir = self.run_dir(run_index)
        if work_dir.exists():
            raise ReproError(
                f"运行目录已存在，拒绝覆盖以防状态泄漏: {work_dir}。"
                f"请更换实验 ID 或使用断点恢复。"
            )
        work_dir.mkdir(parents=True)
        return RunState(
            run_id=f"run_{run_index:03d}",
            run_index=run_index,
            seed=seed,
            work_dir=work_dir,
            prompt=self.config["experiment"]["prompt"],
            rng=random.Random(seed),
            pair_id=pair_id,
            replicate_id=replicate_id,
        )

    def load_for_resume(
        self,
        run_index: int,
        seed: int,
        checkpoint: Dict[str, Any],
        pair_id: int = 1,
        replicate_id: int = 1,
    ) -> RunState:
        """从断点恢复运行状态（运行目录已存在是预期行为）。"""
        work_dir = self.run_dir(run_index)
        work_dir.mkdir(parents=True, exist_ok=True)
        state = RunState(
            run_id=f"run_{run_index:03d}",
            run_index=run_index,
            seed=seed,
            work_dir=work_dir,
            prompt=self.config["experiment"]["prompt"],
            rng=random.Random(seed),
            pair_id=pair_id,
            replicate_id=replicate_id,
        )
        state.rounds_actual = int(checkpoint.get("round", 0))
        state.best_score = checkpoint.get("best_score")
        state.current_score = state.best_score
        state.rollback_count = int(checkpoint.get("rollback_count", 0))
        state.no_improvement_count = int(checkpoint.get("no_improvement_count", 0))
        return state

    def archive_existing(self, run_index: int) -> None:
        """将已有运行目录改名归档，保留失败证据后允许从头重试。"""
        from datetime import datetime

        work_dir = self.run_dir(run_index)
        if work_dir.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = self.runs_root / f"{work_dir.name}_attempt_{stamp}"
            work_dir.rename(target)
