"""审计日志。

- 实验级审计日志：``logs/experiment.log``
- 运行级审计日志：``<run_dir>/audit.log``（每轮生成/评价/修改/回退都会记录）

中间日志仅用于实验审计，不纳入主要图像相似度统计（相似度只对最终图像计算）。
"""

from __future__ import annotations

import logging
from pathlib import Path


def _file_logger(path: Path, name: str, console: bool) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)

    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
        logger.addHandler(ch)

    return logger


def setup_experiment_logger(logs_dir: Path, console: bool = True) -> logging.Logger:
    """实验级审计日志。"""
    return _file_logger(Path(logs_dir) / "experiment.log", "experiment", console)


def setup_run_logger(run_dir: Path) -> logging.Logger:
    """运行级审计日志（仅写文件，避免测试输出噪声）。"""
    return _file_logger(Path(run_dir) / "audit.log", f"run.{Path(run_dir).name}", console=False)
