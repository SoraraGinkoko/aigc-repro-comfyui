"""验证：失败被显式记录，不计为成功，也不静默跳过。"""

import unittest

from aicg_repro.errors import GeneratorError
from aicg_repro.generators.mock_generator import MockGenerator

from .common import TempExperiment, make_config, run


class _AlwaysFailGenerator(MockGenerator):
    def generate(self, prompt, seed, run_state):
        raise GeneratorError("模拟后端持续故障")


class _FlakyGenerator(MockGenerator):
    def __init__(self, fail_times: int, **kwargs):
        super().__init__(**kwargs)
        self._fail_remaining = fail_times

    def generate(self, prompt, seed, run_state):
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise GeneratorError("模拟瞬时故障")
        return super().generate(prompt, seed, run_state)


class FailureRecordingTest(unittest.TestCase):
    def test_failure_recorded_not_counted_as_success(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=1)
            result = run(cfg, te.exp_dir, generator_factory=lambda: _AlwaysFailGenerator(image_size=(16, 16)))
            m = result.manifests[0]
            self.assertEqual(m["status"], "failed")
            self.assertIsNotNone(m["error"])
            self.assertEqual(m["error"]["type"], "GeneratorError")
            self.assertEqual(result.success_count, 0)
            self.assertEqual(result.failed_count, 1)
            # 失败运行仍写 manifest，供审计
            self.assertTrue((te.exp_dir / "runs" / "run_001" / "manifest.json").exists())

    def test_retry_then_success(self):
        with TempExperiment() as te:
            cfg = make_config(
                num_runs=1,
                error_handling={"max_retries": 3, "retry_backoff_seconds": 0.0,
                                "checkpoint_enabled": True, "abort_on_failure": False},
            )
            gen = _FlakyGenerator(fail_times=1, image_size=(16, 16))
            result = run(cfg, te.exp_dir, generator_factory=lambda: gen)
            self.assertEqual(result.manifests[0]["status"], "success")

    def test_retry_exhausted_fails(self):
        with TempExperiment() as te:
            cfg = make_config(
                num_runs=1,
                error_handling={"max_retries": 2, "retry_backoff_seconds": 0.0,
                                "checkpoint_enabled": True, "abort_on_failure": False},
            )
            result = run(cfg, te.exp_dir, generator_factory=lambda: _AlwaysFailGenerator(image_size=(16, 16)))
            m = result.manifests[0]
            self.assertEqual(m["status"], "failed")
            self.assertIn("2 次重试", m["error"]["message"])


if __name__ == "__main__":
    unittest.main()
