"""CLIP 评分评价器（真实技术指标，可插拔）。

用 CLIP（ViT 图像/文本编码器）计算生成图像与提示词的余弦相似度作为
**技术质量分数**（确定性强、可复现）。该分数是纯技术指标，**不代表**任何
法律意义上的独创性判断（两者必须严格区分）。

依赖 ``transformers`` + ``torch``（ComfyUI 环境自带）；未安装时抛出
``EvaluatorError``，绝不编造分数。
"""

from __future__ import annotations

from typing import Any

from ..errors import EvaluatorError
from .base import BaseEvaluator, Evaluation


class ClipScoreEvaluator(BaseEvaluator):
    name = "clip"
    IS_MOCK = False

    def __init__(self, clip_model: str = "openai/clip-vit-base-patch32", device: str = "cuda"):
        self.clip_model = clip_model
        self.device = device
        self._model = None
        self._processor = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch  # noqa: F401
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as exc:  # pragma: no cover - 依赖环境
            raise EvaluatorError(
                "CLIP 评分需要 transformers + torch，当前环境未安装，不计算、不编造分数。"
            ) from exc
        self._model = CLIPModel.from_pretrained(self.clip_model)
        self._processor = CLIPProcessor.from_pretrained(self.clip_model)
        self._model.to(self.device).eval()

    @staticmethod
    def _pil(image: Any) -> Any:
        """从 GeneratedImage 或 PIL Image 中取出 PIL Image。"""
        return image.image if hasattr(image, "image") else image

    def evaluate(self, image: Any, prompt: str, run_state: Any) -> Evaluation:
        self._load()
        import torch

        pil_image = self._pil(image)
        inputs = self._processor(
            text=[prompt],
            images=pil_image,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=77,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self._model(**inputs)
        score = float(outputs.logits_per_image.item())
        return Evaluation(
            score=score,
            metrics={"clip_model": self.clip_model},
            note="CLIP 图像-文本相似度（纯技术指标，不构成法律独创性判断）",
        )
