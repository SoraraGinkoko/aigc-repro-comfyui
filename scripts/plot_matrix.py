"""把各项相似度指标画成 10×10 矩阵热力图（论文插图用）。

读取某次实验的 pairwise_pairs.csv，对每个指标画一张 10×10 矩阵，
横纵轴均为 run_001 … run_010，对角线为自比较。
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# 中文字体
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

EXP = Path("runs/exp_20261020_162214_d3ccf61b")
PAIRS_CSV = EXP / "reports" / "pairwise_pairs.csv"
OUT = Path("assets/metrics_matrix.png")

# (字段, 标题, colormap, 相似类?: True=越大越相似)
METRICS = [
    ("pixel_similarity", "像素相似度", "Blues", True),
    ("ssim", "SSIM 结构相似性", "Blues", True),
    ("pixel_mae", "像素 MAE（平均绝对误差）", "Reds", False),
    ("lpips", "LPIPS 感知距离", "Reds", False),
]


def main() -> None:
    rows = list(csv.DictReader(open(PAIRS_CSV, encoding="utf-8-sig")))
    n = 10
    labels = [f"run_{i:03d}" for i in range(1, n + 1)]

    mats: dict[str, np.ndarray] = {m: np.full((n, n), np.nan) for m, _, _, _ in METRICS}
    for r in rows:
        i, j = int(r["i"]) - 1, int(r["j"]) - 1
        for m, _, _, _ in METRICS:
            v = float(r[m])
            mats[m][i, j] = v
            mats[m][j, i] = v
    for m, _, _, is_sim in METRICS:
        for k in range(n):
            mats[m][k, k] = 1.0 if is_sim else 0.0

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    axes = axes.flatten()
    for ax, (m, title, cmap, is_sim) in zip(axes, METRICS):
        data = mats[m]
        vmin, vmax = float(np.nanmin(data)), float(np.nanmax(data))
        im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_xticks(range(n))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticks(range(n))
        ax.set_yticklabels(labels)
        ax.set_xlabel("run（横轴：被比较对象）")
        ax.set_ylabel("run（纵轴：被比较对象）")
        direction = "越大越相似" if is_sim else "越小越相似"
        ax.set_title(f"{title}\n（{direction}）", fontsize=11)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        # 单元格数值标注
        for i in range(n):
            for j in range(n):
                v = data[i, j]
                norm = (v - vmin) / (vmax - vmin) if vmax > vmin else 0.5
                color = "white" if norm > 0.65 else "black"
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6, color=color)
    fig.suptitle(
        "10 次独立创作最终图像两两相似度矩阵（对角线为自比较）", fontsize=14, y=0.98
    )
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200)
    print("saved", OUT)


if __name__ == "__main__":
    main()
