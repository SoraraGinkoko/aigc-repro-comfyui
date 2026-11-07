"""2×2 消融矩阵：Canny（无/有）× Seg（无/有），四个指标各一格（Nature/NPG 配色）。"""

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

# 行：Canny（0=无，1=有）；列：Seg（0=无，1=有）
GROUPS = {
    (0, 0): "runs/exp_20261022_232653_fd42e4b9",  # 无 Canny 无 Seg（光提示词）
    (0, 1): "runs/exp_20261022_234703_d8b72ab2",  # 无 Canny 有 Seg（仅 seg）
    (1, 0): "runs/exp_20261020_162214_d3ccf61b",  # 有 Canny 无 Seg（仅 canny）
    (1, 1): "runs/exp_20261022_171154_e2d5e477",  # 有 Canny 有 Seg（canny+seg）
}

CMAP_BLUE = LinearSegmentedColormap.from_list("npg_blue", ["#FFFFFF", "#3C5488"])
CMAP_RED = LinearSegmentedColormap.from_list("npg_red", ["#FFFFFF", "#E64B35"])

METRICS = [
    ("pixel_similarity", CMAP_BLUE, "越大越相似 ↑"),
    ("ssim", CMAP_BLUE, "越大越相似 ↑"),
    ("lpips", CMAP_RED, "越小越相似 ↓"),
    ("dreamsim", CMAP_RED, "越小越相似 ↓"),
]
OUT = "assets/ablation_matrix.png"


def pair_mean(exp: str, metric: str) -> float:
    p = Path(exp) / "reports" / "pairwise_pairs.csv"
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    return float(np.mean([float(r[metric]) for r in rows]))


def main() -> None:
    labels_x = ["Seg−", "Seg+"]
    labels_y = ["Canny−", "Canny+"]
    table = {}

    fig, axes = plt.subplots(2, 2, figsize=(12, 11))
    for ax, (metric, cmap, direction) in zip(axes.flatten(), METRICS):
        mat = np.zeros((2, 2))
        for (r, c), exp in GROUPS.items():
            mat[r, c] = pair_mean(exp, metric)
        table[metric] = mat
        im = ax.imshow(mat, cmap=cmap, vmin=0.0, vmax=1.0)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(labels_x)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(labels_y)
        ax.set_title(f"{metric}\n（{direction}）", fontsize=11)
        for r in range(2):
            for c in range(2):
                ax.text(c, r, f"{mat[r, c]:.3f}", ha="center", va="center", fontsize=12,
                        color="white" if mat[r, c] > 0.5 else "black")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(OUT, dpi=300, bbox_inches="tight")

    print("saved", OUT)
    for metric in table:
        m = table[metric]
        print(f"{metric}: 无C无S={m[0,0]:.3f} 无C有S={m[0,1]:.3f} 有C无S={m[1,0]:.3f} 有C有S={m[1,1]:.3f}")


if __name__ == "__main__":
    main()
