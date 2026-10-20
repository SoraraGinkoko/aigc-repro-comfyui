"""MOCK_ONLY 模拟生成器。

明确声明：
- 本生成器 **不调用任何真实生成式 AI 模型**；
- 产出为确定性的伪随机图案 + ``MOCK_ONLY`` 水印；
- 仅用于验证实验工作流与报告管线，**绝不误报为真实图像生成实验**。

确定性保证：
    给定 ``(prompt, seed, round)``，输出完全一致。因此在 ``fixed`` 种子策略下，
    多次独立运行会得到字节级相同的最终图像（用于验证「工具的确定性」）；
    在 ``run_index`` / ``random`` 策略下则会产生不同最终图像（用于观察可变性）。
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .base import BaseGenerator, GeneratedImage


class MockGenerator(BaseGenerator):
    name = "mock"
    IS_MOCK = True  # MOCK_ONLY 标记：manifest 与报告必须透传

    def __init__(self, image_size=(256, 256), watermark="MOCK_ONLY"):
        self.image_size = tuple(int(x) for x in image_size)
        self.watermark = watermark
        self._calls = 0

    def reset(self) -> None:
        self._calls = 0

    # ------------------------------------------------------------------ #
    # 接口实现
    # ------------------------------------------------------------------ #
    def generate(self, prompt: str, seed: int, run_state: Any) -> GeneratedImage:
        self._calls += 1
        img = self._render(seed, 0, prompt)
        return GeneratedImage(
            image=img,
            format="PNG",
            metadata={
                "mock_only": True,
                "generator": self.name,
                "seed": seed,
                "round": 0,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                "call": self._calls,
            },
        )

    def modify(
        self,
        current: GeneratedImage,
        feedback: Any,
        seed: int,
        round_index: int,
        run_state: Any,
    ) -> GeneratedImage:
        self._calls += 1
        img = self._perturb(current.image.copy(), seed, round_index)
        self._watermark(img, f"{self.watermark} seed={seed} r={round_index}")
        return GeneratedImage(
            image=img,
            format="PNG",
            metadata={
                "mock_only": True,
                "generator": self.name,
                "seed": seed,
                "round": round_index,
                "call": self._calls,
                "feedback_score": getattr(feedback, "score", None),
            },
        )

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    def _render(self, seed: int, round_index: int, prompt: str) -> Image.Image:
        rng = random.Random(f"{seed}:{round_index}:{prompt}")
        w, h = self.image_size
        base = Image.new("RGB", (w, h))
        px = base.load()
        for y in range(h):
            for x in range(w):
                px[x, y] = (
                    x * 255 // max(w - 1, 1),
                    y * 255 // max(h - 1, 1),
                    (x + y) * 255 // max(w + h - 2, 1),
                )
        noise = Image.frombytes("RGB", (w, h), rng.randbytes(w * h * 3))
        img = Image.blend(base, noise, alpha=0.35)
        self._watermark(img, f"{self.watermark} seed={seed} r={round_index}")
        return img

    def _perturb(self, img: Image.Image, seed: int, round_index: int) -> Image.Image:
        rng = random.Random(f"{seed}:{round_index}:perturb")
        w, h = img.size
        noise = Image.frombytes("RGB", (w, h), rng.randbytes(w * h * 3))
        # 扰动幅度随轮次递减，仅为演示「收敛」流程，不具真实含义
        alpha = max(0.05, 0.25 - 0.01 * round_index)
        return Image.blend(img, noise, alpha=alpha)

    def _watermark(self, img: Image.Image, text: str) -> None:
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        draw.text((4, 4), text, fill=(255, 255, 0), font=font)
