"""临时脚本：计算某次实验 3 张最终图的两两相似度，并复制到 assets。"""

import shutil
from pathlib import Path

from PIL import Image

from aicg_repro.comparison import compute_pair_metrics, sha256_file

EXP = r"runs\exp_20261020_122935_dcda1800\runs"


def main() -> None:
    base = Path(EXP)
    runs = sorted([p for p in base.iterdir() if p.is_dir() and (p / "final.png").exists()])
    imgs = [p / "final.png" for p in runs]

    print("=== 最终图 ===")
    for p in imgs:
        im = Image.open(p)
        print(f"  {p.parent.name}  {im.size}  sha256={sha256_file(p)[:16]}")

    print("=== 两两比较 C({n},2)={m} 组 ===".format(n=len(imgs), m=len(imgs) * (len(imgs) - 1) // 2))
    for i in range(len(imgs)):
        for j in range(i + 1, len(imgs)):
            m = compute_pair_metrics(imgs[i], imgs[j])
            print(
                f"  {imgs[i].parent.name} vs {imgs[j].parent.name}: "
                f"sha256_equal={m['sha256_equal']}, pixel_sim={m['pixel_similarity']}, "
                f"ssim={m['ssim']}, lpips={m['lpips']}"
            )

    for k, p in enumerate(imgs, 1):
        dst = Path("assets") / f"library_run{k:03d}.png"
        shutil.copy(p, dst)
        print("copied", dst)


if __name__ == "__main__":
    main()
