"""结果比较模块。

- SHA-256 文件哈希：字节级一致性（直接可用）。
- 解码后像素一致性：解码为 RGB 后比较（直接使用 Pillow）。
- SSIM / LPIPS：预留接口。后端（numpy+scikit-image / lpips+torch）未安装时
  抛出 :class:`MetricUnavailableError`，**不编造数值**。

原则：本模块只计算客观指标，不自行定义阈值，也不导出实验结论。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageStat

from .errors import MetricUnavailableError

# --------------------------------------------------------------------------- #
# 基础指标
# --------------------------------------------------------------------------- #


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_rgb(path: str | Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def pixel_consistency(path_a: str | Path, path_b: str | Path) -> dict:
    """解码后像素一致性。返回客观数值，不做阈值判断。"""
    a = _decode_rgb(path_a)
    b = _decode_rgb(path_b)
    size_match = a.size == b.size
    if not size_match:
        w, h = min(a.width, b.width), min(a.height, b.height)
        a = a.crop((0, 0, w, h))
        b = b.crop((0, 0, w, h))
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    mae = sum(stat.mean) / 3.0  # 三通道平均绝对误差
    extrema = diff.getextrema()
    max_abs = max(mx for _, mx in extrema)
    return {
        "size_match": bool(size_match),
        "exact_match": bool(max_abs == 0),
        "mean_abs_error": round(float(mae), 6),
        "max_abs_error": int(max_abs),
        "comparison_size": [a.width, a.height],
    }


def sha256_equal(path_a: str | Path, path_b: str | Path) -> float:
    """字节级一致性：完全相同为 1.0，否则 0.0。"""
    return 1.0 if sha256_file(path_a) == sha256_file(path_b) else 0.0


def pixel_similarity(path_a: str | Path, path_b: str | Path) -> float:
    """像素相似度 = 1 - MAE/255（越高越相似，取值 0~1）。"""
    pc = pixel_consistency(path_a, path_b)
    return round(1.0 - pc["mean_abs_error"] / 255.0, 6)


# --------------------------------------------------------------------------- #
# 预留接口：SSIM / LPIPS（后端就绪时真实计算，否则明确报错，绝不编造）
# --------------------------------------------------------------------------- #


def ssim(path_a: str | Path, path_b: str | Path) -> float:
    """结构相似性 SSIM（预留接口，需 numpy + scikit-image）。"""
    try:
        from skimage import img_as_float
        from skimage.metrics import structural_similarity
    except ImportError as exc:  # pragma: no cover - 依赖环境
        raise MetricUnavailableError(
            "SSIM 为预留接口：当前环境未安装 numpy + scikit-image，不计算、不编造数值。"
        ) from exc

    a = img_as_float(_decode_rgb(path_a))
    b = img_as_float(_decode_rgb(path_b))
    if a.shape != b.shape:
        h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
        a, b = a[:h, :w], b[:h, :w]
    return float(structural_similarity(a, b, channel_axis=-1, data_range=1.0))


def lpips(path_a: str | Path, path_b: str | Path) -> float:
    """感知相似度 LPIPS（真实计算，需 lpips + torch + torchvision）。

    返回值为**感知距离**（越小越相似）；后端缺失时抛 MetricUnavailableError。
    """
    try:
        import lpips
        import torch
        from torchvision import transforms
    except ImportError as exc:  # pragma: no cover - 依赖环境
        raise MetricUnavailableError(
            "LPIPS 为预留接口：当前环境未安装 lpips + torch + torchvision，不计算、不编造数值。"
        ) from exc

    try:
        loss_fn = lpips.LPIPS(net="alex")
        loss_fn.eval()

        def _to_tensor(p: str | Path):
            img = _decode_rgb(p).resize((256, 256))  # AlexNet 输入尺寸
            tf = transforms.Compose(
                [transforms.ToTensor(), transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))]
            )
            return tf(img).unsqueeze(0)

        with torch.no_grad():
            dist = loss_fn(_to_tensor(path_a), _to_tensor(path_b))
        return float(dist.item())
    except MetricUnavailableError:
        raise
    except Exception as exc:  # 下载骨干权重失败/缓存目录不可写等，降级为不可用
        raise MetricUnavailableError(
            f"LPIPS 计算失败（可能需要下载 torchvision 骨干权重到缓存目录）：{exc}"
        ) from exc


# --------------------------------------------------------------------------- #
# 汇总与矩阵
# --------------------------------------------------------------------------- #


def compute_pair_metrics(path_a: str | Path, path_b: str | Path) -> dict:
    """计算一对图像的全部可用指标；不可用指标记为 None（不编造）。"""
    out: dict = {}
    out["sha256_equal"] = sha256_equal(path_a, path_b)
    pc = pixel_consistency(path_a, path_b)
    out["pixel_mae"] = pc["mean_abs_error"]
    out["pixel_max_abs"] = pc["max_abs_error"]
    out["pixel_exact"] = 1.0 if pc["exact_match"] else 0.0
    out["pixel_similarity"] = round(1.0 - pc["mean_abs_error"] / 255.0, 6)
    for name, fn in (("ssim", ssim), ("lpips", lpips)):
        try:
            out[name] = fn(path_a, path_b)
        except MetricUnavailableError:
            out[name] = None
    return out


def build_matrix(
    paths: Sequence[str | Path], metric_fn: Callable[[str, str], float]
) -> Tuple[List[List[float]], List[Tuple[int, int, float]]]:
    """构造 N×N 对称矩阵，并返回 C(N,2) 组两两比较对（i < j）。"""
    n = len(paths)
    mat = [[0.0] * n for _ in range(n)]
    pairs: List[Tuple[int, int, float]] = []
    for i in range(n):
        mat[i][i] = metric_fn(paths[i], paths[i])
        for j in range(i + 1, n):
            v = metric_fn(paths[i], paths[j])
            mat[i][j] = v
            mat[j][i] = v
            pairs.append((i, j, v))
    return mat, pairs
