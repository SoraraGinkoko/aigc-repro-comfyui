"""运行 manifest 与软件版本收集。

每次运行都会写出 ``manifest.json``，记录：实际轮数、随机种子、配置快照、
软件版本、运行状态、最终输出路径、错误信息等，供审计与复现。
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from PIL import Image

from .version import PROJECT_NAME, __version__


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_capture(cmd: list, timeout: int = 15) -> Any:
    """受控执行外部命令并返回 stdout；任何失败返回 None（不静默影响主流程）。"""
    import subprocess

    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def collect_software_versions() -> Dict[str, str]:
    versions = {
        "project": PROJECT_NAME,
        "project_version": __version__,
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "pillow": getattr(Image, "__version__", "unknown"),
        "platform": platform.platform(),
    }
    # torch / GPU（仅真实后端环境存在；缺失时如实标注）
    try:
        import torch

        versions["torch"] = torch.__version__
        versions["torch_cuda_available"] = str(torch.cuda.is_available())
        versions["torch_cuda_version"] = str(getattr(torch.version, "cuda", "unknown"))
        if torch.cuda.is_available():
            versions["gpu_name"] = torch.cuda.get_device_name(0)
            versions["gpu_vram_gb"] = str(
                round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)
            )
    except Exception:
        versions["torch"] = "not-installed"
    # NVIDIA 驱动版本（nvidia-smi）
    drv = _run_capture(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    if drv:
        versions["nvidia_driver"] = drv.splitlines()[0].strip()
    return versions


def collect_comfyui_version(config: Dict[str, Any]) -> Any:
    """记录 ComfyUI 的 git commit（配置了 comfyui_dir 且为 git 仓库时）。"""
    if config["generator"]["type"] != "comfyui":
        return None
    comfy_dir = config["generator"].get("comfyui_dir")
    if not comfy_dir:
        return None
    return _run_capture(["git", "-C", comfy_dir, "rev-parse", "HEAD"])


def write_json(path: Path, data: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_run_manifest(run_dir: Path, data: Dict[str, Any]) -> Path:
    return write_json(run_dir / "manifest.json", data)


def read_run_manifest(run_dir: Path) -> Dict[str, Any]:
    return read_json(run_dir / "manifest.json")


def collect_model_hashes(config: Dict[str, Any]) -> Dict[str, str]:
    """记录真实后端模型文件的 SHA-256。

    模型文件缺失时抛 ConfigError（绝不静默跳过）。仅对 ``comfyui`` 生成器生效。
    """
    if config["generator"]["type"] != "comfyui":
        return {}
    from .comparison import sha256_file
    from .errors import ConfigError

    g = config["generator"]
    models_dir = Path(g.get("models_dir", "D:/ComfyUI/models"))
    specs = [
        ("checkpoint", "checkpoints", g["checkpoint"]),
        ("controlnet", "controlnet", g["controlnet"]),
    ]
    out: Dict[str, str] = {}
    for key, subdir, fname in specs:
        p = models_dir / subdir / fname
        if not p.exists():
            raise ConfigError(f"模型文件缺失: {p}（不得静默跳过，请先完成安装）")
        out[f"{key}:{fname}"] = sha256_file(p)
    return out


def write_config_snapshot(experiment_dir: Path, snapshot: Dict[str, Any]) -> Path:
    return write_json(experiment_dir / "config_snapshot.json", snapshot)


def write_experiment_meta(experiment_dir: Path, meta: Dict[str, Any]) -> Path:
    return write_json(experiment_dir / "experiment.json", meta)
