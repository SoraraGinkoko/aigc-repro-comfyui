"""MOCK 评价器。

返回确定性的伪质量分数（图像字节的 SHA-256 哈希映射到 [0,1)），
仅用于验证「生成 -> 评价 -> 修改/回退」控制流程，不具任何真实美学/语义含义。
"""

from __future__ import annotations

import hashlib
from typing import Any

from .base import BaseEvaluator, Evaluation


class MockEvaluator(BaseEvaluator):
    name = "mock"
    IS_MOCK = True

    def evaluate(self, image: Any, prompt: str, run_state: Any) -> Evaluation:
        if hasattr(image, "to_bytes"):
            data = image.to_bytes()
        else:
            data = image.tobytes()
        digest = hashlib.sha256(data).hexdigest()
        score = int(digest[:8], 16) % 1_000_000 / 1_000_000.0
        return Evaluation(
            score=score,
            metrics={"sha256": digest},
            note="MOCK 确定性伪质量分数（图像哈希映射，仅用于流程验证）",
        )
