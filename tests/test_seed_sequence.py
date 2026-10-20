"""验证：预设种子序列的确定性、落盘加载与校验。"""

import unittest

from aicg_repro.errors import ConfigError
from aicg_repro.seeds import generate_seed_sequence, load_seed_sequence, save_seed_sequence

from .common import PROJECT_ROOT, TempExperiment


class SeedSequenceTest(unittest.TestCase):
    def test_generate_is_deterministic(self):
        a = generate_seed_sequence(20, base_seed=0)
        b = generate_seed_sequence(20, base_seed=0)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 20)

    def test_presaved_file_matches_generator(self):
        cfg_seq = load_seed_sequence(PROJECT_ROOT / "config" / "seed_sequence.json")
        self.assertEqual(len(cfg_seq), 20)
        self.assertEqual(cfg_seq, generate_seed_sequence(20, base_seed=0))

    def test_save_load_roundtrip(self):
        with TempExperiment() as te:
            seq = [1, 2, 3, 5]
            p = te.root / "seq.json"
            save_seed_sequence(p, seq)
            self.assertEqual(load_seed_sequence(p), seq)

    def test_load_missing_raises(self):
        with self.assertRaises(ConfigError):
            load_seed_sequence("no_such_seed_sequence.json")


if __name__ == "__main__":
    unittest.main()
