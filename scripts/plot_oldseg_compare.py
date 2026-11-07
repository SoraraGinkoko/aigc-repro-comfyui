"""无语义分割 vs 有语义分割：四指标柱状图（Nature/NPG 配色风格）。"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "Arial", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["font.size"] = 11
matplotlib.rcParams["axes.linewidth"] = 0.8
matplotlib.rcParams["xtick.direction"] = "out"
matplotlib.rcParams["ytick.direction"] = "out"

A = "runs/exp_20261020_162214_d3ccf61b"  # 无语义分割
B = "runs/exp_20261022_171154_e2d5e477"  # 有语义分割
METRICS = ["pixel_similarity", "ssim", "lpips", "dreamsim"]
OUT = "assets/oldseg_barchart.png"

# NPG (Nature Publishing Group) palette
C_A = "#3C5488"  # 深蓝
C_B = "#E64B35"  # 砖红


def pair_mean(exp: str, metric: str) -> float:
    p = Path(exp) / "reports" / "pairwise_pairs.csv"
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    return float(np.mean([float(r[metric]) for r in rows]))


def main() -> None:
    x = np.arange(len(METRICS))
    w = 0.34
    a = [pair_mean(A, m) for m in METRICS]
    b = [pair_mean(B, m) for m in METRICS]

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.bar(x - w / 2, a, w, label="无语义分割", color=C_A, edgecolor="white",
           linewidth=0.6, zorder=3)
    ax.bar(x + w / 2, b, w, label="有语义分割", color=C_B, edgecolor="white",
           linewidth=0.6, zorder=3)

    for i, (av, bv) in enumerate(zip(a, b)):
        ax.text(i - w / 2, av, f"{av:.3f}", ha="center", va="bottom", fontsize=8.5)
        ax.text(i + w / 2, bv, f"{bv:.3f}", ha="center", va="bottom", fontsize=8.5)

    ax.set_xticks(x)
    ax.set_xticklabels(METRICS)
    ax.set_ylabel("均值")
    ax.set_ylim(0, max(max(a), max(b)) * 1.15)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(width=0.8, length=4)

    ax.grid(axis="y", color="#DDDDDD", linewidth=0.6, linestyle="--", zorder=0)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper right")

    fig.tight_layout()
    fig.savefig(OUT, dpi=300)
    print("saved", OUT)


if __name__ == "__main__":
    main()
