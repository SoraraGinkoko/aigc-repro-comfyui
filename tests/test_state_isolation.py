"""验证：状态重置与跨运行隔离，防止上一轮工作状态泄漏。"""

import unittest
from pathlib import Path

from aicg_repro.errors import ReproError
from aicg_repro.state import StateManager

from .common import TempExperiment, make_config, run


class StateIsolationTest(unittest.TestCase):
    def test_runs_have_isolated_directories(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=2, max_iterations_per_run=2)
            result = run(cfg, te.exp_dir)
            self.assertEqual(result.success_count, 2)
            dirs = sorted(p.name for p in (te.exp_dir / "runs").glob("run_*") if p.is_dir())
            self.assertEqual(dirs, ["run_001", "run_002"])
            # 各自拥有独立审计日志与 manifest
            for d in dirs:
                self.assertTrue((te.exp_dir / "runs" / d / "audit.log").exists())
                self.assertTrue((te.exp_dir / "runs" / d / "manifest.json").exists())

    def test_fresh_states_are_independent(self):
        with TempExperiment() as te:
            cfg = make_config()
            sm = StateManager(te.exp_dir, cfg)
            s1 = sm.fresh(1, seed=1)
            s2 = sm.fresh(2, seed=2)
            self.assertIsNot(s1, s2)
            self.assertIsNot(s1.rng, s2.rng)
            self.assertNotEqual(s1.work_dir, s2.work_dir)
            # 修改一个状态不应影响另一个
            s1.history.append("x")
            s1.rollback_count = 99
            self.assertEqual(s2.history, [])
            self.assertEqual(s2.rollback_count, 0)

    def test_fresh_rejects_existing_dir(self):
        with TempExperiment() as te:
            cfg = make_config()
            sm = StateManager(te.exp_dir, cfg)
            sm.fresh(1, seed=1)
            with self.assertRaises(ReproError):
                sm.fresh(1, seed=2)

    def test_seed_strategy_run_index_is_stable(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=2, random={"strategy": "run_index", "master_seed": 7})
            result = run(cfg, te.exp_dir)
            seeds = [m["seed"] for m in result.manifests]
            self.assertEqual(seeds, [8, 9])  # master_seed + run_index


if __name__ == "__main__":
    unittest.main()
