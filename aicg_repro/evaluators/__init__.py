"""评价器：可替换接口与实现。"""

from .base import BaseEvaluator, Evaluation
from .clip_evaluator import ClipScoreEvaluator
from .mock_evaluator import MockEvaluator

__all__ = ["BaseEvaluator", "Evaluation", "MockEvaluator", "ClipScoreEvaluator"]
