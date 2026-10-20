"""可替换生成器接口。

真实后端（ComfyUI 等）应实现同样的 :class:`BaseGenerator` 接口。
第一阶段仅提供明确标记为 ``MOCK_ONLY`` 的模拟生成器；任何实现都必须
通过 ``IS_MOCK`` 显式声明是否属于模拟数据，禁止将模拟数据误报为真实图像生成。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict

from PIL import Image


@dataclass
class GeneratedImage:
    """生成器产出的一张图像及元数据。"""

    image: Image.Image
    format: str = "PNG"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.image.save(buf, format=self.format)
        return buf.getvalue()

    def save(self, path: Path | str) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(p, format=self.format)
        return p


class BaseGenerator(ABC):
    """生成器抽象接口。"""

    name: str = "base"
    IS_MOCK: bool = False

    @abstractmethod
    def reset(self) -> None:
        """每次运行前重置内部状态，防止跨运行污染。"""

    @abstractmethod
    def generate(self, prompt: str, seed: int, run_state: Any) -> GeneratedImage:
        """生成初始图像。"""

    @abstractmethod
    def modify(
        self,
        current: GeneratedImage,
        feedback: Any,
        seed: int,
        round_index: int,
        run_state: Any,
    ) -> GeneratedImage:
        """基于评价反馈修改图像，进入下一轮。"""
