"""验证：CLIP 评价器能正确从 GeneratedImage 解包出 PIL Image。"""

import unittest

from PIL import Image

from aicg_repro.evaluators.clip_evaluator import ClipScoreEvaluator
from aicg_repro.generators.base import GeneratedImage


class ClipEvaluatorTest(unittest.TestCase):
    def test_unwrap_generated_image(self):
        pil = Image.new("RGB", (8, 8), "white")
        gi = GeneratedImage(image=pil)
        self.assertIs(ClipScoreEvaluator._pil(gi), pil)

    def test_unwrap_pil_passthrough(self):
        pil = Image.new("RGB", (8, 8), "white")
        self.assertIs(ClipScoreEvaluator._pil(pil), pil)


if __name__ == "__main__":
    unittest.main()
