"""验证：最终图像归档正确、可解码、哈希一致，且中间产物用于审计。"""

import unittest
from pathlib import Path

from PIL import Image

from aicg_repro.comparison import sha256_file

from .common import TempExperiment, make_config, run


class FinalImageArchiveTest(unittest.TestCase):
    def test_final_image_archived(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=1, max_iterations_per_run=2)
            result = run(cfg, te.exp_dir)
            m = result.manifests[0]
            self.assertEqual(m["status"], "success")
            fp = Path(m["final_output_path"])
            self.assertTrue(fp.exists())
            self.assertEqual(fp.name, "final.png")
            # 可解码且为 PNG
            with Image.open(fp) as img:
                img.load()
                self.assertEqual(img.format, "PNG")
            # manifest 哈希与磁盘文件一致
            self.assertEqual(m["final_sha256"], sha256_file(fp))
            # 中间产物用于审计（断点 + 审计日志）
            run_dir = fp.parent
            self.assertTrue((run_dir / "checkpoint.json").exists())
            self.assertTrue((run_dir / "best.png").exists())
            self.assertTrue((run_dir / "current.png").exists())
            self.assertTrue((run_dir / "audit.log").exists())

    def test_final_image_is_mock_only(self):
        with TempExperiment() as te:
            cfg = make_config(num_runs=1, max_iterations_per_run=1)
            result = run(cfg, te.exp_dir)
            m = result.manifests[0]
            # 组件声明 MOCK，避免误报为真实图像生成
            self.assertTrue(m["components"]["is_mock"])
            self.assertTrue(m["components"]["evaluator_is_mock"])


if __name__ == "__main__":
    unittest.main()
