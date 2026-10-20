"""验证：种子簿的确定性、互不重复、无平移重叠、落盘加载。"""

import unittest

from aicg_repro.seeds import generate_seed_book, load_seed_book, save_seed_book

from .common import TempExperiment


class SeedBookTest(unittest.TestCase):
    def test_generate_deterministic(self):
        a = generate_seed_book(20, 20, 20240601)
        b = generate_seed_book(20, 20, 20240601)
        self.assertEqual(a, b)

    def test_all_seeds_distinct(self):
        book = generate_seed_book(20, 20, 20240601)
        flat = [s for seq in book for s in seq]
        self.assertEqual(len(flat), 400)
        self.assertEqual(len(set(flat)), 400)  # 全部互不重复

    def test_no_overlap_between_sequences(self):
        book = generate_seed_book(10, 20, 1)
        for i in range(len(book)):
            si = set(book[i])
            for j in range(i + 1, len(book)):
                self.assertFalse(si & set(book[j]))  # 任意两条无交集（即无重复、无平移重叠）

    def test_save_load_roundtrip(self):
        with TempExperiment() as te:
            book = generate_seed_book(4, 5, 7)
            p = te.root / "book.json"
            save_seed_book(p, book)
            self.assertEqual(load_seed_book(p), book)


if __name__ == "__main__":
    unittest.main()
