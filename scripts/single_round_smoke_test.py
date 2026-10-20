#!/usr/bin/env python3
"""单轮生成冒烟测试：验证 ComfyUI 服务、SD1.5、Canny ControlNet 可用，生成一张图像。

用法（先启动 scripts\\run_comfyui.ps1，服务监听 127.0.0.1:8188）：

    C:\\Users\\32089\\anaconda3\\envs\\comfyui\\python.exe scripts\\single_round_smoke_test.py

成功标志：打印「单轮生成成功」并写出 runs/_smoke_single_round.png。
"""

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from aicg_repro.build import build_generator
from aicg_repro.comparison import sha256_bytes
from aicg_repro.config import load_config
from aicg_repro.manifest import (
    collect_comfyui_version,
    collect_model_hashes,
    collect_software_versions,
)


def main() -> int:
    cfg = load_config(PROJECT_ROOT / "config" / "comfyui_experiment_config.json")
    print("=== 软件环境 ===")
    for k, v in collect_software_versions().items():
        print(f"  {k}: {v}")
    print("=== 模型哈希 ===")
    for k, v in collect_model_hashes(cfg).items():
        print(f"  {k}: {v}")
    print("=== ComfyUI commit ===", collect_comfyui_version(cfg))

    gen = build_generator(cfg)
    state = SimpleNamespace(seed=cfg["random"]["master_seed"])
    img = gen.generate(cfg["experiment"]["prompt"], state.seed, state)

    out = PROJECT_ROOT / "runs" / "_smoke_single_round.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.image.save(out)
    print("=== 单轮生成成功 ===")
    print(f"  output: {out}")
    print(f"  size:   {img.image.size}")
    print(f"  sha256: {sha256_bytes(img.to_bytes())[:16]}...")
    print(f"  seed:   {img.metadata['seed']}  is_mock={img.metadata['is_mock']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
