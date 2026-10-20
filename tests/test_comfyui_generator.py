"""验证：ComfyUI 生成器（用假 HTTP 传输，无需真实服务）。"""

import io
import unittest
from types import SimpleNamespace
from typing import Any, Dict, List

from PIL import Image

from aicg_repro.errors import GeneratorError
from aicg_repro.generators.comfyui_generator import ComfyUIGenerator


def _png_bytes(size=(16, 16)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, "PNG")
    return buf.getvalue()


class FakeTransport:
    """模拟 ComfyUI HTTP API：记录提交的工作流，返回可控结果。"""

    def __init__(self, image_bytes: bytes = None, fail: bool = False):
        self.posted_prompts: List[Dict[str, Any]] = []
        self.history_polls = 0
        self.image_bytes = image_bytes or _png_bytes()
        self.fail = fail

    def post_json(self, path, payload):
        assert path == "/prompt"
        self.posted_prompts.append(payload["prompt"])
        return {"prompt_id": "test-prompt-id"}

    def get_json(self, path):
        self.history_polls += 1
        if self.fail:
            return {"test-prompt-id": {"status": {"status_str": "error", "messages": [["x", "boom", {}]]}}}
        if self.history_polls >= 2:
            return {
                "test-prompt-id": {
                    "status": {"status_str": "success"},
                    "outputs": {"11": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
                }
            }
        return {}

    def get_bytes(self, path):
        return self.image_bytes


def comfyui_config(**overrides) -> Dict[str, Any]:
    cfg = {
        "experiment": {"prompt": "a balance scale", "name": "t", "tags": []},
        "generator": {
            "type": "comfyui",
            "server_url": "http://127.0.0.1:8188",
            "checkpoint": "v1-5-pruned-emaonly.safetensors",
            "controlnet": "control_v11p_sd15_canny.pth",
            "control_image": "control_image.png",
            "negative_prompt": "bad",
            "width": 512,
            "height": 512,
            "sampler": "euler",
            "scheduler": "normal",
            "steps": 20,
            "cfg": 7.0,
            "control_strength": 1.0,
            "canny_low": 100,
            "canny_high": 200,
            "poll_interval_seconds": 0.001,
            "poll_timeout_seconds": 1.0,
        },
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


class ComfyUIGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.gen = ComfyUIGenerator(
            comfyui_config(), transport=self.transport, seed_sequence=[111, 222, 333, 444]
        )
        self.run_state = SimpleNamespace(seed=0)

    def test_generate_uses_first_seed_and_marks_real(self):
        img = self.gen.generate("prompt", 0, self.run_state)
        workflow = self.transport.posted_prompts[0]
        self.assertEqual(workflow["9"]["inputs"]["seed"], 111)
        self.assertEqual(img.metadata["seed"], 111)
        self.assertFalse(img.metadata["is_mock"])
        self.assertIsInstance(img.image, Image.Image)

    def test_modify_uses_round_seed_from_sequence(self):
        current = self.gen.generate("prompt", 0, self.run_state)
        img = self.gen.modify(current, None, 0, round_index=2, run_state=self.run_state)
        workflow = self.transport.posted_prompts[-1]
        self.assertEqual(workflow["9"]["inputs"]["seed"], 222)  # 第 2 轮 -> sequence[1]
        self.assertEqual(img.metadata["seed"], 222)

    def test_workflow_contains_expected_nodes(self):
        self.gen.generate("prompt", 0, self.run_state)
        w = self.transport.posted_prompts[0]
        self.assertEqual(w["1"]["class_type"], "CheckpointLoaderSimple")
        self.assertEqual(w["1"]["inputs"]["ckpt_name"], "v1-5-pruned-emaonly.safetensors")
        self.assertEqual(w["4"]["inputs"]["control_net_name"], "control_v11p_sd15_canny.pth")
        self.assertEqual(w["2"]["inputs"]["image"], "control_image.png")
        self.assertEqual(w["9"]["inputs"]["steps"], 20)
        self.assertEqual(w["9"]["inputs"]["cfg"], 7.0)
        self.assertEqual(w["7"]["inputs"]["strength"], 1.0)
        self.assertEqual(w["9"]["class_type"], "KSampler")
        self.assertEqual(w["11"]["class_type"], "SaveImage")
        # 默认不启用 Canny 预处理：无节点 3，控制图直接取自 LoadImage
        self.assertNotIn("3", w)
        self.assertEqual(w["7"]["inputs"]["image"], ["2", 0])

    def test_canny_preprocess_enabled_adds_canny_node(self):
        transport = FakeTransport()
        gen = ComfyUIGenerator(
            comfyui_config(generator={"use_canny_preprocess": True, "canny_low": 0.4, "canny_high": 0.8}),
            transport=transport,
            seed_sequence=[1],
        )
        gen.generate("prompt", 0, self.run_state)
        w = transport.posted_prompts[0]
        self.assertEqual(w["3"]["class_type"], "Canny")
        self.assertEqual(w["3"]["inputs"]["low_threshold"], 0.4)
        self.assertEqual(w["3"]["inputs"]["high_threshold"], 0.8)
        self.assertEqual(w["7"]["inputs"]["image"], ["3", 0])

    def test_poll_error_raises_generator_error(self):
        gen = ComfyUIGenerator(comfyui_config(), transport=FakeTransport(fail=True), seed_sequence=[1])
        with self.assertRaises(GeneratorError):
            gen.generate("prompt", 0, self.run_state)

    def test_timeout_raises_generator_error(self):
        class NeverDone(FakeTransport):
            def get_json(self, path):
                return {}

        gen = ComfyUIGenerator(
            comfyui_config(poll_interval_seconds=0.001, poll_timeout_seconds=0.02),
            transport=NeverDone(),
            seed_sequence=[1],
        )
        with self.assertRaises(GeneratorError):
            gen.generate("prompt", 0, self.run_state)


if __name__ == "__main__":
    unittest.main()
