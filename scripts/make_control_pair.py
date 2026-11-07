"""从新源照片生成控制图：Canny 边缘图 + 语义分割图（保持原图比例 512×320）。"""

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from skimage.color import rgb2gray
from skimage.feature import canny
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

SRC = Path("assets/library.png")
W, H = 512, 320
EDGE = Path("assets/library_edges.png")
SEG = Path("assets/library_seg.png")


def main() -> None:
    img = Image.open(SRC).convert("RGB").resize((W, H), Image.LANCZOS)
    img.save("assets/library_512x320.png")

    # 1) Canny 边缘图
    gray = rgb2gray(np.asarray(img))
    edges = canny(gray, sigma=2.0)
    Image.fromarray((edges * 255).astype(np.uint8)).save(EDGE)
    print("edges saved:", EDGE, "ratio=", round(float(edges.mean()), 4))

    # 2) SegFormer-b3 语义分割
    proc = SegformerImageProcessor.from_pretrained("nvidia/segformer-b3-finetuned-ade-512-512")
    model = SegformerForSemanticSegmentation.from_pretrained(
        "nvidia/segformer-b3-finetuned-ade-512-512"
    )
    model.eval()
    inputs = proc(images=img, return_tensors="pt")
    with torch.no_grad():
        out = model(**inputs)
    up = torch.nn.functional.interpolate(
        out.logits, size=(H, W), mode="bilinear", align_corners=False
    )
    pred = up.argmax(1)[0].numpy()

    pal = np.zeros((150, 3), dtype=np.uint8)
    for i in range(150):
        pal[i] = [(i * 37) % 256, (i * 89) % 256, (i * 151) % 256]
    Image.fromarray(pal[pred]).save(SEG)

    labels = model.config.id2label
    ids, counts = np.unique(pred, return_counts=True)
    print("=== 分割类别 ===")
    for i, c in zip(ids.tolist(), counts.tolist()):
        print(f"  {i:>3} : {labels.get(int(i), '?'):<20} : {c}")
    print("seg saved:", SEG)


if __name__ == "__main__":
    main()
