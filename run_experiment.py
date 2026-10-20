#!/usr/bin/env python3
"""实验 CLI 入口。

用法::

    python run_experiment.py --config config/experiment_config.json
    python run_experiment.py --config config/experiment_config.json --resume
    python run_experiment.py --config config/experiment_config.json --experiment-id my_exp

为避免覆盖已有结果：
- 未指定 ``--experiment-id`` 时自动生成唯一 ID；
- 指定且已存在时默认拒绝覆盖，除非同时给出 ``--force``（不推荐）或 ``--resume``。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aicg_repro.config import config_snapshot, load_config, new_experiment_id
from aicg_repro.controller import ExperimentController
from aicg_repro.manifest import write_config_snapshot, write_experiment_meta, utcnow_iso
from aicg_repro.reporting import generate_reports


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AIGC 可复现性实验（同一创作者独立重复创作 / 固定种子复现）")
    parser.add_argument("--config", default="config/experiment_config.json", help="JSON 配置文件路径")
    parser.add_argument("--experiment-id", default=None, help="显式实验 ID；已存在时默认拒绝覆盖")
    parser.add_argument("--resume", action="store_true", help="断点恢复未完成的运行")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的实验目录（不推荐，破坏审计链）")
    args = parser.parse_args(argv)

    config = load_config(args.config)

    experiment_id = args.experiment_id or new_experiment_id()
    experiment_dir = Path(config["paths"]["output_root"]) / experiment_id
    if experiment_dir.exists() and not (args.resume or args.force):
        print(
            f"[错误] 实验目录已存在，拒绝覆盖: {experiment_dir}\n"
            f"       请更换 --experiment-id，或使用 --resume 断点恢复。",
            file=sys.stderr,
        )
        return 2

    experiment_dir.mkdir(parents=True, exist_ok=True)
    write_config_snapshot(experiment_dir, config_snapshot(config))
    write_experiment_meta(
        experiment_dir,
        {
            "experiment_id": experiment_id,
            "name": config["experiment"]["name"],
            "created_at": utcnow_iso(),
            "phase": "1",
            "mock_only": True,
        },
    )

    num_runs = config["num_runs"]
    n_pairs = config.get("num_pairs")
    if n_pairs:
        num_runs = n_pairs * config["replicates_per_pair"]

    print(f"实验 ID: {experiment_id}")
    print(f"实验目录: {experiment_dir}")
    if n_pairs:
        print(f"配对组数: {n_pairs} | 每对复制: {config['replicates_per_pair']} | 总创作次数: {num_runs}")
    print(f"运行次数: {num_runs} | 每轮上限: {config['max_iterations_per_run']} | "
          f"种子策略: {config['random']['strategy']}")

    controller = ExperimentController(config, experiment_dir)
    result = controller.run_all(resume=args.resume)

    reports = generate_reports(experiment_dir, config, result.manifests)

    print("\n=== 运行汇总 ===")
    print(f"成功: {result.success_count} | 失败: {result.failed_count} | "
          f"总数: {len(result.manifests)}")
    for m in result.manifests:
        status = m["status"]
        stop = m["stop_reason"] or (m.get("error") or {}).get("type") or ""
        print(
            f"  pair {m['pair_id']:>2}/{m['replicate_id']}  run {m['run_index']:>3}  "
            f"{status:<8} rounds={m['rounds_actual']}  stop={stop}"
        )

    print("\n=== 报告产物 ===")
    for key, p in reports.items():
        print(f"  {key:<18} {p}")

    if result.failed_count > 0:
        print("\n[警告] 存在失败运行，已在 manifest 与报告中显式记录，不计为成功。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
