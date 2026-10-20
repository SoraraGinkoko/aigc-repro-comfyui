"""生成器：可替换接口与实现。"""

from .base import BaseGenerator, GeneratedImage
from .comfyui_generator import ComfyUIGenerator
from .mock_generator import MockGenerator

__all__ = ["BaseGenerator", "GeneratedImage", "MockGenerator", "ComfyUIGenerator"]
