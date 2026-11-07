"""把 4 个指标各画成一张独立的 10×10 矩阵图（Nature/NPG 配色风格）。"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "Arial", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["font.size"] = 10

EXP = "runs/exp_20261020_162214_d3ccf61b"
PAIRS = Path(EXP) / "reports" / "pairwise_pairs.csv"
N = 10

# NPG 顺序色阶：白 → 深蓝 / 白 → 砖红
CMAP_BLUE = LinearSegmentedColormap.from_list("npg_blue", ["#FFFFFF", "#3C5488"])
CMAP_RED = LinearSegmentedColormap.from_list("npg_red", ["#FFFFFF", "#E64B35"])

METRICS = [
    ("pixel_similarity", CMAP_BLUE, "越大越相似 ↑"),
    ("ssim", CMAP_BLUE, "越大越相似 ↑"),
    ("lpips", CMAP_RED, "越小越相似 ↓"),
    ("dreamsim", CMAP_RED, "越小越相似 ↓"),
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

    for metric, cmap, direction in METRICS:
        mat = build_matrix(pairs, metric)
        fig, ax = plt.subplots(figsize=(7.2, 6.4))
        im = ax.imshow(mat, cmap=cmap, vmin=0.0, vmax=1.0)

        ax.set_xticks(range(N))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(N))
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("run（被比较对象）")
        ax.set_ylabel("run（被比较对象）")
        ax.set_title(f"{metric}（{direction}）", fontsize=11)

        for spine in ax.spines.values():
            spine.set_linewidth(0.6)
        ax.tick_params(width=0.6, length=3)

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cbar.set_label(direction, fontsize=9)
        cbar.outline.set_linewidth(0.6)

        for i in range(N):
            for j in range(N):
                if i != j:
                    ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center",
                            fontsize=7, color="white" if mat[i, j] > 0.6 else "#333333")

        fig.tight_layout()
        out = f"assets/matrix_{metric}.png"
        fig.savefig(out, dpi=300)
        plt.close(fig)
        print("saved", out)


if __name__ == "__main__":
    main()
