"""验证：N 次独立创作 → 两两比较报告生成。"""

import csv
import unittest
from pathlib import Path

from aicg_repro.reporting import generate_reports

from .common import TempExperiment, make_config, run


class ReportGenerationTest(unittest.TestCase):
    def test_pairwise_reports_generated(self):
        with TempExperiment() as te:
            cfg = make_config(
                num_runs=3,
                replicates_per_pair=1,
                max_iterations_per_run=2,
                random={"strategy": "run_index", "master_seed": 7},
            )
            result = run(cfg, te.exp_dir)
            self.assertEqual(result.success_count, 3)
            reports = generate_reports(te.exp_dir, cfg, result.manifests)
            for key, path in reports.items():
                self.assertTrue(Path(path).exists(), f"{key} 未生成")

            # 状态汇总：表头 + 3 次创作
            with open(reports["runs_summary"], encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), 4)

            # 两两比较：C(3,2)=3 组 + 表头
            with open(reports["pairwise_pairs"], encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), 4)

            # 描述性统计：表头 + 6 指标行
            with open(reports["descriptive_stats"], encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), 7)

            # 每轮记录：3 次 × 2 轮 = 6 行 + 表头
            with open(reports["round_history"], encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), 1 + 3 * 2)

            # HTML 内容
            html = Path(reports["html"]).read_text(encoding="utf-8")
            self.assertIn("两两比较", html)

    def test_seed_sequences_recorded(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=3, replicates_per_pair=1, max_iterations_per_run=1)
            result = run(cfg, te.exp_dir)
            self.assertEqual(result.success_count, 3)
            for m in result.manifests:
                self.assertIn("seed_sequence", m)
                self.assertIn("seed_sequence_index", m)


if __name__ == "__main__":
    unittest.main()
