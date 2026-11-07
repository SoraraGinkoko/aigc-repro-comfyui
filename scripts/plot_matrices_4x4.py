"""附录用：横版 4×4（行=组，列=指标）的 10×10 矩阵大图。"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

matplotlib.rcParams["font.family"] = ["Times New Roman", "SimSun"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["font.size"] = 8

GROUPS = [
    ("无 Canny 无 Seg", "runs/exp_20261022_232653_fd42e4b9"),
    ("无 Canny 有 Seg", "runs/exp_20261022_234703_d8b72ab2"),
    ("有 Canny 无 Seg", "runs/exp_20261020_162214_d3ccf61b"),
    ("有 Canny 有 Seg", "runs/exp_20261022_171154_e2d5e477"),
]
METRICS = [
    ("pixel_similarity", "越大越相似 ↑"),
    ("ssim", "越大越相似 ↑"),
    ("lpips", "越小越相似 ↓"),
    ("dreamsim", "越小越相似 ↓"),
]
CMAP_BLUE = LinearSegmentedColormap.from_list("npg_blue", ["#FFFFFF", "#3C5488"])
CMAP_RED = LinearSegmentedColormap.from_list("npg_red", ["#FFFFFF", "#E64B35"])
N = 10
OUT = "assets/matrices_4x4.png"


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


def load_pairs(exp):
    p = Path(exp) / "reports" / "pairwise_pairs.csv"
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def main() -> None:
    labels = [f"run_{i+1:03d}" for i in range(N)]
    fig, axes = plt.subplots(4, 4, figsize=(17, 15))

    for r, (gname, exp) in enumerate(GROUPS):
        pairs = load_pairs(exp)
        for c, (metric, direction) in enumerate(METRICS):
            ax = axes[r][c]
            mat = build_matrix(pairs, metric)
            cmap = CMAP_RED if metric in ("lpips", "dreamsim") else CMAP_BLUE
            im = ax.imshow(mat, cmap=cmap, vmin=0.0, vmax=1.0)

            ax.set_xticks(range(N))
            ax.set_yticks(range(N))
            if r == 3:
                ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=5.5)
            else:
                ax.set_xticklabels([])
            if c == 0:
                ax.set_yticklabels(labels, fontsize=5.5)
            else:
                ax.set_yticklabels([])

            # 顶部列标题（仅第一行）
            if r == 0:
                ax.set_title(f"{metric}（{direction}）", fontsize=9)
            # 左侧行标题（仅第一列）
            if c == 0:
                ax.set_ylabel(gname, fontsize=9)

            for i in range(N):
                for j in range(N):
                    if i != j:
                        ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center",
                                fontsize=5, color="white" if mat[i, j] > 0.5 else "black")

            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig.tight_layout()
    fig.savefig(OUT, dpi=200)
    print("saved", OUT)


if __name__ == "__main__":
    main()
