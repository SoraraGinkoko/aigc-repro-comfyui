"""指标矩阵图（4 项，色标 0–1）：像素相似度、SSIM、LPIPS、DreamSim，标注方向。"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

EXP = "runs/exp_20261020_162214_d3ccf61b"
PAIRS = Path(EXP) / "reports" / "pairwise_pairs.csv"
OUT = "assets/metrics_matrix.png"
N = 10

# (字段, colormap, 方向说明)
METRICS = [
    ("pixel_similarity", "Blues", "越大越相似 ↑"),
    ("ssim", "Blues", "越大越相似 ↑"),
    ("lpips", "Reds", "越小越相似 ↓"),
    ("dreamsim", "Reds", "越小越相似 ↓"),
]


def build_matrix(pairs, metric):
    mat = np.full((N, N), np.nan)
    for r in pairs:
        i, j = int(r["i"]) - 1, int(r["j"]) - 1
        v = float(r[metric])
        mat[i, j] = v
        mat[j, i] = v
    for k in range(N):
        mat[k, k] = 1.0 if metric in ("pixel_similarity", "ssim") else 0.0
    return mat


def main() -> None:
    pairs = list(csv.DictReader(open(PAIRS, encoding="utf-8-sig")))
    labels = [f"run_{i+1:03d}" for i in range(N)]

    fig, axes = plt.subplots(2, 2, figsize=(13, 12.5))
    axes = axes.flatten()
    for ax, (metric, cmap, direction) in zip(axes, METRICS):
        mat = build_matrix(pairs, metric)
        im = ax.imshow(mat, cmap=cmap, vmin=0.0, vmax=1.0)
        ax.set_xticks(range(N))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(N))
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("run（被比较对象）")
        ax.set_ylabel("run（被比较对象）")
        ax.set_title(f"{metric}\n（{direction}）", fontsize=11)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(direction)
        for i in range(N):
            for j in range(N):
                if i != j:
                    ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=6,
                            color="white" if mat[i, j] > 0.6 else "black")
    fig.suptitle("10×10 两两相似度矩阵（色标 0–1，对角线为自比较）", fontsize=13, y=0.995)
    fig.tight_layout()
    fig.savefig(OUT, dpi=200)
    print("saved", OUT)


if __name__ == "__main__":
    main()
