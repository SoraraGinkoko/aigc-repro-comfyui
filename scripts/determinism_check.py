"""同一种子序列跑 3 遍：检查最终图是否字节级可复现（不生成报告）。

用法::

    python scripts/determinism_check.py

步骤：
1. 取 config/seed_book.json 的 sequence[0]，复制 3 份保存为 config/seed_book_same3.json；
2. 用 config/determinism_check_config.json 跑 3 次创作（同一序列）；
3. 计算 3 张最终图的 SHA-256，判定是否字节级完全一致；
4. 复制到 assets/determinism_run*.png。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from aicg_repro.comparison import sha256_file
from aicg_repro.config import config_snapshot, load_config, new_experiment_id
from aicg_repro.controller import ExperimentController
from aicg_repro.manifest import utcnow_iso, write_config_snapshot, write_experiment_meta
from aicg_repro.seeds import load_seed_book, save_seed_book

CONFIG = "config/determinism_check_config.json"
SRC_BOOK = "config/seed_book.json"
SAME_BOOK = "config/seed_book_same3.json"


def main() -> int:
    # 1) 生成「3 条相同序列」的种子簿
    book = load_seed_book(SRC_BOOK)
    seq0 = book[0]
    save_seed_book(SAME_BOOK, [list(seq0) for _ in range(3)])
    print(f"已生成 {SAME_BOOK}（3 条相同序列，首种子 = {seq0[0]}）")

    config = load_config(CONFIG)
    experiment_id = new_experiment_id()
    experiment_dir = Path(config["paths"]["output_root"]) / experiment_id
    experiment_dir.mkdir(parents=True, exist_ok=True)
    write_config_snapshot(experiment_dir, config_snapshot(config))
    write_experiment_meta(
        experiment_dir,
        {
            "experiment_id": experiment_id,
            "name": config["experiment"]["name"],
            "created_at": utcnow_iso(),
            "phase": "determinism-check",
            "mock_only": config["generator"]["type"] == "mock",
        },
    )
    print(f"实验 ID: {experiment_id}")

    controller = ExperimentController(config, experiment_dir)
    result = controller.run_all()
    print(f"成功: {result.success_count} | 失败: {result.failed_count}")

    finals = []
    for m in result.manifests:
        if m["status"] == "success":
            p = Path(m["final_output_path"])
            finals.append((m["run_index"], p))
            print(f"  run_{m['run_index']:03d}  sha256={sha256_file(p)[:16]}  rounds={m['rounds_actual']}")

    hashes = [sha256_file(p) for _, p in finals]
    n_unique = len(set(hashes))
    verdict = "字节级完全一致（可复现）" if n_unique == 1 else "不一致（存在非确定性）"
    print(f"=== 判定：{len(hashes)} 张最终图，唯一哈希数 = {n_unique} → {verdict} ===")

    for idx, (ri, p) in enumerate(finals, 1):
        dst = Path("assets") / f"determinism_run{idx:02d}.png"
        shutil.copy(p, dst)
        print("copied", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
