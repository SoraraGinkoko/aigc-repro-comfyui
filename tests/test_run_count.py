"""验证：独立运行次数、manifest 与最终图像归档。"""

import unittest
from pathlib import Path

from aicg_repro.manifest import read_run_manifest

from .common import TempExperiment, make_config, run


class RunCountTest(unittest.TestCase):
    def test_num_runs(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=3, max_iterations_per_run=2)
            result = run(cfg, te.exp_dir)
            self.assertEqual(len(result.manifests), 3)
            self.assertEqual(result.success_count, 3)
            self.assertEqual(result.failed_count, 0)
            for m in result.manifests:
                run_dir = te.exp_dir / "runs" / m["run_id"]
                self.assertTrue((run_dir / "manifest.json").exists())
                self.assertTrue(Path(m["final_output_path"]).exists())

    def test_manifest_records_required_fields(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=1, max_iterations_per_run=2)
            result = run(cfg, te.exp_dir)
            m = result.manifests[0]
            for key in (
                "run_id", "status", "seed", "seed_strategy", "rounds_actual",
                "stop_reason", "final_output_path", "final_sha256",
                "config_snapshot", "software_versions", "started_at", "finished_at",
            ):
                self.assertIn(key, m)
            # manifest 文件内容与返回结果一致
            disk = read_run_manifest(te.exp_dir / "runs" / m["run_id"])
            self.assertEqual(disk["status"], "success")
            self.assertEqual(disk["final_sha256"], m["final_sha256"])
            # 配置快照已保存
            self.assertIn("num_runs", disk["config_snapshot"])


if __name__ == "__main__":
    unittest.main()
