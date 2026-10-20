"""根据配置构建生成器 / 评价器实例。

第一阶段支持 ``mock``；第二阶段支持 ``comfyui``（真实后端）与 ``clip``（真实评价）。
种子序列由控制器按 ``pair/replicate`` 注入，构建器不自行加载种子。
"""

from __future__ import annotations

from typing import Any, Dict

from .errors import ConfigError
from .evaluators.base import BaseEvaluator
from .evaluators.clip_evaluator import ClipScoreEvaluator
from .evaluators.mock_evaluator import MockEvaluator
from .generators.base import BaseGenerator
from .generators.comfyui_generator import ComfyUIGenerator
from .generators.mock_generator import MockGenerator


def build_generator(config: Dict[str, Any]) -> BaseGenerator:
    gen_type = config["generator"]["type"]
    if gen_type == "mock":
        m = config["generator"].get("mock", {})
        return MockGenerator(
            image_size=tuple(m.get("image_size", [256, 256])),
            watermark=m.get("watermark", "MOCK_ONLY"),
        )
    if gen_type == "comfyui":
        return ComfyUIGenerator(config)  # 种子序列由控制器注入
    raise ConfigError(f"不支持的生成器类型: {gen_type!r}（支持 mock / comfyui）")


def build_evaluator(config: Dict[str, Any]) -> BaseEvaluator:
    ev_type = config["evaluator"]["type"]
    if ev_type == "mock":
        return MockEvaluator()
    if ev_type == "clip":
        opts = config["evaluator"].get("clip", {})
        return ClipScoreEvaluator(
            clip_model=opts.get("clip_model", "openai/clip-vit-base-patch32"),
            device=opts.get("device", "cuda"),
        )
    raise ConfigError(f"不支持的评价器类型: {ev_type!r}（支持 mock / clip）")
