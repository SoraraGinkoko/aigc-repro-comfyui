"""集成测试：控制器 + ComfyUI 生成器（假传输）+ 种子簿注入 + manifest 容错。

验证真实后端接入后，从「控制器 → 按 pair/replicate 注入种子序列 → 每轮种子记录 → manifest」的
完整链路，以及模型文件缺失时 manifest 的错误记录（不崩溃、不静默跳过）。
"""

import unittest

from aicg_repro.config import load_config
from aicg_repro.controller import ExperimentController
from aicg_repro.generators.comfyui_generator import ComfyUIGenerator
from aicg_repro.seeds import save_seed_book

from .common import TempExperiment
from .test_comfyui_generator import FakeTransport


def _full_comfyui_config(models_dir: str, **overrides) -> dict:
    cfg = load_config()  # 完整默认配置
    cfg["generator"].update(
        {
            "type": "comfyui",
            "server_url": "http://127.0.0.1:8188",
            "comfyui_dir": "D:/ComfyUI",
            "models_dir": models_dir,
            "checkpoint": "v1-5-pruned-emaonly.safetensors",
            "controlnet": "control_v11p_sd15_canny_fp16.safetensors",
            "control_image": "control_image.png",
            "negative_prompt": "bad",
            "width": 16,
            "height": 16,
            "sampler": "euler",
            "scheduler": "normal",
            "steps": 2,
            "cfg": 7.0,
            "control_strength": 1.0,
            "use_canny_preprocess": False,
            "canny_low": 0.4,
            "canny_high": 0.8,
            "poll_interval_seconds": 0.001,
            "poll_timeout_seconds": 1.0,
        }
    )
    cfg["error_handling"].update({"max_retries": 0, "retry_backoff_seconds": 0.0})
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


class ComfyUIIntegrationTest(unittest.TestCase):
    def test_full_pipeline_records_seed_and_survives_missing_models(self):
        with TempExperiment() as te:
            cfg = _full_comfyui_config(
                models_dir=str(te.root / "no_such_models"),
                num_runs=2,
                max_iterations_per_run=2,
                rollback={"enabled": False, "max_consecutive_rollbacks": 99, "tolerance": 0.0},
            )

            def factory():
                return ComfyUIGenerator(cfg, transport=FakeTransport(), seed_sequence=[111, 222, 333])

            controller = ExperimentController(cfg, te.exp_dir, generator_factory=factory)
            result = controller.run_all()

            self.assertEqual(len(result.manifests), 2)
            self.assertEqual(result.success_count, 2)
            self.assertEqual(
                [(m["pair_id"], m["replicate_id"]) for m in result.manifests],
                [(1, 1), (1, 2)],
            )
            for m in result.manifests:
                self.assertEqual(m["status"], "success")
                self.assertFalse(m["components"]["is_mock"])
                # 无种子簿时，保留工厂注入的序列：轮1=111，轮2=222
                self.assertEqual([r["seed"] for r in m["history"]], [111, 222])
                self.assertIn("error", m["model_hashes"])  # 模型缺失被记录，而非崩溃
                self.assertEqual(m["config_snapshot"]["generator"]["type"], "comfyui")

    def test_seed_book_injected_per_run(self):
        with TempExperiment() as te:
            book_path = te.root / "seed_book.json"
            save_seed_book(book_path, [[101, 102, 103], [201, 202, 203]])
            cfg = _full_comfyui_config(
                models_dir=str(te.root / "no_such_models"),
                num_runs=2,
                max_iterations_per_run=2,
                rollback={"enabled": False, "max_consecutive_rollbacks": 99, "tolerance": 0.0},
                generator={"seed_book_file": str(book_path)},
            )

            def factory():
                return ComfyUIGenerator(cfg, transport=FakeTransport())

            controller = ExperimentController(cfg, te.exp_dir, generator_factory=factory)
            result = controller.run_all()

            seeds = [[r["seed"] for r in m["history"]] for m in result.manifests]
            self.assertEqual(seeds[0], [101, 102])  # run1 用序列 0
            self.assertEqual(seeds[1], [201, 202])  # run2 用序列 1
            self.assertEqual(result.manifests[0]["seed_sequence"], [101, 102, 103])
            self.assertEqual(result.manifests[1]["seed_sequence"], [201, 202, 203])


if __name__ == "__main__":
    unittest.main()
