#!/usr/bin/env python3
"""本地预检脚本：正式实验前一次性校验环境、模型与种子簿。

用法（先启动 run_comfyui.ps1）：

    C:\\Users\\32089\\anaconda3\\envs\\comfyui\\python.exe scripts\\preflight_check.py [配置文件路径]

默认校验 config/pair_experiment_config.json。逐项输出 OK/FAIL；全部 OK 才建议开始正式实验。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from aicg_repro.config import load_config
from aicg_repro.manifest import collect_comfyui_version, collect_model_hashes
from aicg_repro.seeds import load_seed_book, load_seed_sequence

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def main() -> int:
    cfg_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else PROJECT_ROOT / "config" / "pair_experiment_config.json"
    )
    if not cfg_path.is_absolute():
        cfg_path = PROJECT_ROOT / cfg_path
    cfg = load_config(cfg_path)
    g = cfg["generator"]

    # 1. ComfyUI 服务可达
    try:
        import json
        import urllib.request

        with urllib.request.urlopen(f"{g['server_url']}/system_stats", timeout=5) as resp:
            stats = json.loads(resp.read().decode("utf-8"))
        dev = (stats.get("devices") or [{}])[0]
        check("ComfyUI 服务可达", True, f"vram_total={dev.get('vram_total')} name={dev.get('name')}")
    except Exception as exc:
        check("ComfyUI 服务可达", False, str(exc))

    # 2. 模型文件存在 + 哈希
    try:
        hashes = collect_model_hashes(cfg)
        ok = "error" not in hashes
        check("模型文件存在且可哈希", ok, str(hashes)[:200])
    except Exception as exc:
        check("模型文件存在且可哈希", False, str(exc))

    # 3. ComfyUI git commit
    commit = collect_comfyui_version(cfg)
    check("ComfyUI git commit", bool(commit), commit or "未检出")

    # 4. 控制图已复制到 input 目录
    input_img = Path(g.get("comfyui_dir", "D:/ComfyUI")) / "input" / g["control_image"]
    check("控制图在 ComfyUI input 目录", input_img.exists(), str(input_img))

    # 5. 种子簿 / 种子序列
    n_creations = (
        int(cfg["num_pairs"]) * int(cfg["replicates_per_pair"])
        if cfg.get("num_pairs")
        else int(cfg["num_runs"])
    )
    if g.get("seed_book_file"):
        try:
            book = load_seed_book(PROJECT_ROOT / g["seed_book_file"])
            flat = [s for seq in book for s in seq]
            ok = len(book) >= n_creations and len(flat) == len(set(flat))
            check("种子簿加载且互不重复", ok, f"序列数={len(book)}（需 >= {n_creations}），全部互异={len(flat)==len(set(flat))}")
        except Exception as exc:
            check("种子簿加载", False, str(exc))
    elif g.get("seed_sequence_file"):
        try:
            seq = load_seed_sequence(PROJECT_ROOT / g["seed_sequence_file"])
            check("种子序列加载", len(seq) >= int(cfg["max_iterations_per_run"]), f"length={len(seq)}")
        except Exception as exc:
            check("种子序列加载", False, str(exc))

    # 6. 输出目录可写
    out_dir = PROJECT_ROOT / cfg["paths"]["output_root"]
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        check("输出目录可写", True, str(out_dir))
    except Exception as exc:
        check("输出目录可写", False, str(exc))

    # 7. torch / CUDA
    try:
        import torch

        check(
            "PyTorch + CUDA",
            torch.cuda.is_available(),
            f"torch={torch.__version__} cuda={torch.version.cuda} gpu={torch.cuda.get_device_name(0)}",
        )
    except Exception as exc:
        check("PyTorch + CUDA", False, str(exc))

    # 8. SSIM / LPIPS 后端
    try:
        import skimage.metrics  # noqa: F401

        check("SSIM 后端 (scikit-image)", True)
    except Exception as exc:
        check("SSIM 后端 (scikit-image)", False, str(exc))
    try:
        import lpips  # noqa: F401

        check("LPIPS 后端 (lpips)", True)
    except Exception as exc:
        check("LPIPS 后端 (lpips)", False, str(exc))

    print("\n=== 汇总 ===")
    failed = [n for n, ok, _ in results if not ok]
    if failed:
        print("存在失败项:", ", ".join(failed))
        return 1
    print("全部通过，可开始实验。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
