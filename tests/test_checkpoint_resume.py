"""验证：断点记录与断点恢复（安全重试机制）。"""

import unittest

from aicg_repro.controller import ExperimentController
from aicg_repro.errors import GeneratorError
from aicg_repro.generators.mock_generator import MockGenerator

from .common import TempExperiment, make_config, run


class _FailAfterN(MockGenerator):
    """在第 N 次调用（generate/modify）时抛出异常，模拟中断。"""

    def __init__(self, fail_at_call: int, **kwargs):
        super().__init__(**kwargs)
        self._call = 0
        self.fail_at_call = fail_at_call

    def _tick(self):
        self._call += 1
        if self._call == self.fail_at_call:
            raise GeneratorError("模拟中断")

    def generate(self, prompt, seed, run_state):
        self._tick()
        return super().generate(prompt, seed, run_state)

    def modify(self, current, feedback, seed, round_index, run_state):
        self._tick()
        return super().modify(current, feedback, seed, round_index, run_state)


class CheckpointResumeTest(unittest.TestCase):
    def test_checkpoint_saved_each_round(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=1, max_iterations_per_run=3)
            run(cfg, te.exp_dir)
            ckpt = te.exp_dir / "runs" / "run_001" / "checkpoint.json"
            self.assertTrue(ckpt.exists())

    def test_resume_from_checkpoint(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=1, max_iterations_per_run=5)
            # 第一次运行在第 3 次调用（第 3 轮 modify）失败
            gen = _FailAfterN(fail_at_call=3, image_size=(16, 16))
            result1 = run(cfg, te.exp_dir, generator_factory=lambda: gen)
            m1 = result1.manifests[0]
            self.assertEqual(m1["status"], "failed")
            self.assertEqual(m1["rounds_actual"], 2)  # 断点已落在第 2 轮
            self.assertTrue((te.exp_dir / "runs" / "run_001" / "checkpoint.json").exists())

            # 恢复：使用正常生成器，从断点继续到 max_iterations
            controller2 = ExperimentController(cfg, te.exp_dir)
            result2 = controller2.run_all(resume=True)
            m2 = result2.manifests[0]
            self.assertEqual(m2["status"], "success")
            self.assertEqual(m2["rounds_actual"], 5)
            self.assertEqual(m2["stop_reason"], "max_iterations")


if __name__ == "__main__":
    unittest.main()
