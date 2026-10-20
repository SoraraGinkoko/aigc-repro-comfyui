"""测试公共工具：快速配置与工作区内的临时实验目录。

注意：临时目录用普通 ``pathlib`` 创建于项目根（工作区）内。
沙箱对 ``tempfile.mkdtemp`` 创建的目录会限制其内部写入，故不使用 tempfile。
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from aicg_repro.config import load_config
from aicg_repro.controller import ExperimentController, ExperimentResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_config(**overrides) -> Dict[str, Any]:
    """基于默认配置构造测试配置（小图像、零回退延迟、零重试）。"""
    cfg = load_config()
    cfg["generator"]["mock"]["image_size"] = [16, 16]
    cfg["error_handling"]["retry_backoff_seconds"] = 0.0
    cfg["error_handling"]["max_retries"] = 0
    cfg["num_runs"] = 1
    cfg["max_iterations_per_run"] = 3
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


class TempExperiment:
    """上下文管理器：在工作区内提供隔离的临时实验目录。"""

    def __enter__(self) -> "TempExperiment":
        name = f"test_tmp_{uuid.uuid4().hex[:12]}"
        self.root = PROJECT_ROOT / name
        self.exp_dir = self.root / "runs" / "exp_test"
        self.exp_dir.mkdir(parents=True)
        return self

    def __exit__(self, *args) -> None:
        # 关闭日志文件句柄，确保 Windows 下可删除临时目录
        logging.shutdown()
        shutil.rmtree(self.root, ignore_errors=True)


def run(
    cfg: Dict[str, Any],
    exp_dir: Path,
    generator_factory: Optional[Callable[[], Any]] = None,
    evaluator_factory: Optional[Callable[[], Any]] = None,
) -> ExperimentResult:
    controller = ExperimentController(
        cfg, exp_dir, generator_factory=generator_factory, evaluator_factory=evaluator_factory
    )
    return controller.run_all()
