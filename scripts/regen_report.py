"""重新生成报告（不重跑生成），用于补算 LPIPS 等指标。

用法::

    python scripts/regen_report.py [实验目录] [配置路径]
"""

import json
import sys
from pathlib import Path

from aicg_repro.config import load_config
from aicg_repro.reporting import generate_reports

DEFAULT_EXP = "runs/exp_20261020_162214_d3ccf61b"
DEFAULT_CONFIG = "config/pair_experiment_config.json"


def main() -> int:
    exp_dir = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXP)
    config = load_config(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CONFIG)

    manifests = []
    for run_dir in sorted((exp_dir / "runs").glob("run_*")):
        p = run_dir / "manifest.json"
        if p.exists():
            manifests.append(json.loads(p.read_text(encoding="utf-8")))
    print(f"loaded {len(manifests)} manifests from {exp_dir}")
    if not manifests:
        print("no manifests found")
        return 1

    reports = generate_reports(exp_dir, config, manifests)
    for k, v in reports.items():
        print(f"  {k:<18} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
