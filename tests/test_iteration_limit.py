"""验证：每次运行最多执行 max_iterations_per_run 轮。"""

import unittest

from .common import TempExperiment, make_config, run


class IterationLimitTest(unittest.TestCase):
    def test_stops_at_max_iterations(self):
        with TempExperiment() as te:
            cfg = make_config(
                num_runs=1,
                max_iterations_per_run=5,
                stop_conditions={"quality_threshold": None, "no_improvement_rounds": None},
                rollback={"enabled": False, "max_consecutive_rollbacks": 99, "tolerance": 0.0},
            )
            result = run(cfg, te.exp_dir)
            m = result.manifests[0]
            self.assertEqual(m["status"], "success")
            self.assertEqual(m["rounds_actual"], 5)
            self.assertEqual(m["stop_reason"], "max_iterations")
            # 历史记录也恰好 5 轮
            self.assertEqual(len(m["history"]), 5)

    def test_never_exceeds_limit(self):
        with TempExperiment() as te:
            cfg = make_config(
                num_runs=2,
                max_iterations_per_run=4,
                stop_conditions={"quality_threshold": None, "no_improvement_rounds": None},
                rollback={"enabled": False, "max_consecutive_rollbacks": 99, "tolerance": 0.0},
            )
            result = run(cfg, te.exp_dir)
            for m in result.manifests:
                self.assertLessEqual(m["rounds_actual"], 4)


if __name__ == "__main__":
    unittest.main()
