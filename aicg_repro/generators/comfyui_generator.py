"""ComfyUI 生成器（真实后端，通过 HTTP API 驱动 Canny ControlNet 工作流）。

流程：
- ``POST /prompt`` 提交 workflow JSON；
- ``GET /history/{prompt_id}`` 轮询执行状态；
- ``GET /view?filename=...`` 下载生成图像。

设计要点：
- HTTP 传输可注入（测试时用假传输，无需真实服务）；
- 每轮使用「预先保存的种子序列」中的种子，并写入生成图像元数据供控制器记录；
- 所有实验参数来自配置，代码不临时更改模型/规则；
- 出错抛 ``GeneratorError``，由控制器按配置安全重试，绝不静默跳过。
"""

from __future__ import annotations

import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from PIL import Image

from ..errors import GeneratorError
from .base import BaseGenerator, GeneratedImage


class ComfyUITransport:
    """默认 HTTP 传输（urllib 实现）；测试可替换为假实现。"""

    def __init__(self, server_url: str, timeout: float = 30.0):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout

    def post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.server_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise GeneratorError(f"ComfyUI 请求失败 {path}: {exc}") from exc

    def get_json(self, path: str) -> Dict[str, Any]:
        url = f"{self.server_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise GeneratorError(f"ComfyUI 请求失败 {path}: {exc}") from exc

    def get_bytes(self, path: str) -> bytes:
        url = f"{self.server_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.URLError as exc:
            raise GeneratorError(f"ComfyUI 请求失败 {path}: {exc}") from exc


class ComfyUIGenerator(BaseGenerator):
    """ComfyUI SD1.5 + Canny ControlNet 生成器（真实后端，非 MOCK）。"""

    name = "comfyui"
    IS_MOCK = False  # 真实后端：manifest 与报告必须如实标注

    def __init__(
        self,
        config: Dict[str, Any],
        transport: Optional[ComfyUITransport] = None,
        seed_sequence: Optional[List[int]] = None,
    ):
        g = config["generator"]
        self.server_url = g["server_url"]
        self.checkpoint = g["checkpoint"]
        self.controlnet = g["controlnet"]
        self.control_image = g["control_image"]
        self.prompt = config["experiment"]["prompt"]
        self.negative_prompt = g.get("negative_prompt", "")
        self.width = int(g["width"])
        self.height = int(g["height"])
        self.sampler = g["sampler"]
        self.scheduler = g["scheduler"]
        self.steps = int(g["steps"])
        self.cfg = float(g["cfg"])
        self.control_strength = float(g["control_strength"])
        # Canny 预处理：默认关闭（直接用预生成的白线黑底边缘图，更可复现）。
        # 开启时使用 ComfyUI 归一化阈值（0.01~0.99，默认 0.4/0.8）。
        self.use_canny_preprocess = bool(g.get("use_canny_preprocess", False))
        self.canny_low = float(g.get("canny_low", 0.4))
        self.canny_high = float(g.get("canny_high", 0.8))
        self.poll_interval = float(g.get("poll_interval_seconds", 1.0))
        self.poll_timeout = float(g.get("poll_timeout_seconds", 600.0))
        self.transport = transport or ComfyUITransport(self.server_url)
        self.seed_sequence = seed_sequence or []

    # ------------------------------------------------------------------ #
    # 接口实现
    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        self._calls = 0

    def generate(self, prompt: str, seed: int, run_state: Any) -> GeneratedImage:
        self._calls = getattr(self, "_calls", 0) + 1
        round_seed = self._seed_for_round(run_state, 1)
        img = self._submit(round_seed)
        return GeneratedImage(
            image=img,
            format="PNG",
            metadata={
                "generator": self.name,
                "is_mock": False,
                "seed": round_seed,
                "round": 1,
                "prompt": self.prompt,
            },
        )

    def modify(
        self, current: GeneratedImage, feedback: Any, seed: int, round_index: int, run_state: Any
    ) -> GeneratedImage:
        self._calls = getattr(self, "_calls", 0) + 1
        round_seed = self._seed_for_round(run_state, round_index)
        img = self._submit(round_seed)
        return GeneratedImage(
            image=img,
            format="PNG",
            metadata={
                "generator": self.name,
                "is_mock": False,
                "seed": round_seed,
                "round": round_index,
                "prompt": self.prompt,
            },
        )

    # ------------------------------------------------------------------ #
    # 种子序列
    # ------------------------------------------------------------------ #
    def _seed_for_round(self, run_state: Any, round_number: int) -> int:
        """从预设序列取本轮种子（round_number 为 1 基：第 1 轮取 sequence[0]）。"""
        if self.seed_sequence:
            return int(self.seed_sequence[(round_number - 1) % len(self.seed_sequence)])
        # 无预设序列时的确定性回退：run 种子 + (轮次-1)
        return int(getattr(run_state, "seed", 0)) + (round_number - 1)

    # ------------------------------------------------------------------ #
    # ComfyUI 交互
    # ------------------------------------------------------------------ #
    def _submit(self, seed: int) -> Image.Image:
        workflow = self._build_workflow(seed)
        resp = self.transport.post_json("/prompt", {"prompt": workflow})
        prompt_id = resp.get("prompt_id")
        if not prompt_id:
            raise GeneratorError(f"ComfyUI 未返回 prompt_id: {resp}")
        return self._poll_and_fetch(prompt_id)

    def _poll_and_fetch(self, prompt_id: str) -> Image.Image:
        deadline = time.time() + self.poll_timeout
        while time.time() < deadline:
            hist = self.transport.get_json(f"/history/{prompt_id}")
            entry = hist.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise GeneratorError(f"ComfyUI 执行错误: {status}")
                if entry.get("outputs"):
                    images = self._extract_images(entry["outputs"])
                    if images:
                        return self._download_image(images[0])
            time.sleep(self.poll_interval)
        raise GeneratorError(f"ComfyUI 执行超时 ({self.poll_timeout}s): prompt_id={prompt_id}")

    @staticmethod
    def _extract_images(outputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        for node_output in outputs.values():
            imgs = node_output.get("images")
            if imgs:
                return imgs
        return []

    def _download_image(self, img_info: Dict[str, Any]) -> Image.Image:
        params = urllib.parse.urlencode(
            {
                "filename": img_info["filename"],
                "subfolder": img_info.get("subfolder", ""),
                "type": img_info.get("type", "output"),
            }
        )
        data = self.transport.get_bytes(f"/view?{params}")
        return Image.open(io.BytesIO(data)).convert("RGB")

    # ------------------------------------------------------------------ #
    # 工作流构建（SD1.5 + Canny ControlNet，text-to-image）
    # ------------------------------------------------------------------ #
    def _build_workflow(self, seed: int) -> Dict[str, Any]:
        # 控制图来源：默认直接使用预生成的白线黑底边缘图；可选在线 Canny 预处理。
        if self.use_canny_preprocess:
            control_source: Any = ["3", 0]
            canny_node = {
                "3": {
                    "class_type": "Canny",
                    "inputs": {
                        "image": ["2", 0],
                        "low_threshold": self.canny_low,
                        "high_threshold": self.canny_high,
                    },
                }
            }
        else:
            control_source = ["2", 0]
            canny_node = {}

        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": self.checkpoint}},
            "2": {"class_type": "LoadImage", "inputs": {"image": self.control_image}},
            **canny_node,
            "4": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": self.controlnet}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": self.prompt, "clip": ["1", 1]}},
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": self.negative_prompt, "clip": ["1", 1]},
            },
            "7": {
                "class_type": "ControlNetApplyAdvanced",
                "inputs": {
                    "positive": ["5", 0],
                    "negative": ["6", 0],
                    "control_net": ["4", 0],
                    "image": control_source,
                    "strength": self.control_strength,
                    "start_percent": 0.0,
                    "end_percent": 1.0,
                },
            },
            "8": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": self.width, "height": self.height, "batch_size": 1},
            },
            "9": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["7", 0],
                    "negative": ["7", 1],
                    "latent_image": ["8", 0],
                    "seed": seed,
                    "steps": self.steps,
                    "cfg": self.cfg,
                    "sampler_name": self.sampler,
                    "scheduler": self.scheduler,
                    "denoise": 1.0,
                },
            },
            "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
            "11": {
                "class_type": "SaveImage",
                "inputs": {"images": ["10", 0], "filename_prefix": "aicg_repro"},
            },
        }
