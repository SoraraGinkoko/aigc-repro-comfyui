"""可替换评价器接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Evaluation:
    """一次评价结果。score 为质量分数，语义由具体评价器定义。"""

    score: float
    metrics: Dict[str, Any] = field(default_factory=dict)
    note: str = ""


class BaseEvaluator(ABC):
    name: str = "base"
    IS_MOCK: bool = False

    @abstractmethod
    def evaluate(self, image: Any, prompt: str, run_state: Any) -> Evaluation:
        """对一张图像给出评价。"""
