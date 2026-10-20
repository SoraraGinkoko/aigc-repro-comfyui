"""验证：固定种子下多次运行最终图像字节级一致（工具的确定性），
不同种子下则产生不同最终图像。"""

import unittest

from .common import TempExperiment, make_config, run


class DeterminismTest(unittest.TestCase):
    def test_fixed_seed_identical(self):
        with TempExperiment() as te:
            cfg = make_config(
                num_runs=3,
                max_iterations_per_run=3,
                random={"strategy": "fixed", "master_seed": 123},
                rollback={"enabled": False, "max_consecutive_rollbacks": 99, "tolerance": 0.0},
            )
            result = run(cfg, te.exp_dir)
            self.assertEqual(result.success_count, 3)
            shas = [m["final_sha256"] for m in result.manifests]
            self.assertEqual(len(set(shas)), 1)  # 字节级完全相同

    def test_run_index_seed_distinct(self):
        with TempExperiment() as te:
            cfg = make_config(
                num_runs=3,
                max_iterations_per_run=3,
                random={"strategy": "run_index", "master_seed": 123},
                rollback={"enabled": False, "max_consecutive_rollbacks": 99, "tolerance": 0.0},
            )
            result = run(cfg, te.exp_dir)
            self.assertEqual(result.success_count, 3)
            shas = [m["final_sha256"] for m in result.manifests]
            self.assertEqual(len(set(shas)), 3)  # 不同种子 -> 不同最终图像


if __name__ == "__main__":
    unittest.main()
