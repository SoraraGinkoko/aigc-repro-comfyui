"""用 SegFormer(ADE20K) 对图书馆照片生成语义分割图，先可视化检查区域是否正确。"""

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

SRC = Path("assets/library.png")
OUT = Path("assets/library_seg.png")


def build_palette(n: int = 150) -> np.ndarray:
    """为每类分配可区分颜色（仅用于可视化）。"""
    pal = np.zeros((n, 3), dtype=np.uint8)
    for i in range(n):
        pal[i] = [(i * 37) % 256, (i * 89) % 256, (i * 151) % 256]
    return pal


def main() -> None:
    img = Image.open(SRC).convert("RGB")
    proc = SegformerImageProcessor.from_pretrained("nvidia/segformer-b3-finetuned-ade-512-512")
    model = SegformerForSemanticSegmentation.from_pretrained(
        "nvidia/segformer-b3-finetuned-ade-512-512"
    )
    model.eval()
    inputs = proc(images=img, return_tensors="pt")
    with torch.no_grad():
        out = model(**inputs)
    logits = out.logits
    up = torch.nn.functional.interpolate(
        logits, size=(img.height, img.width), mode="bilinear", align_corners=False
    )
    pred = up.argmax(1)[0].numpy()

    pal = build_palette()
    seg = pal[pred]
    Image.fromarray(seg).save(OUT)

    labels = model.config.id2label
    ids, counts = np.unique(pred, return_counts=True)
    print("=== 检测到的类别（id: 名称 : 像素数）===")
    for i, c in zip(ids.tolist(), counts.tolist()):
        print(f"  {i:>3} : {labels.get(int(i), '?'):<20} : {c}")
    print("saved", OUT)


if __name__ == "__main__":
    main()
