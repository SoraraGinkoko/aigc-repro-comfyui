"""从旧照片（gate.png, 512×512）生成边缘图与 seg 图，供「换图前 + seg」实验使用。"""

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from skimage.color import rgb2gray
from skimage.feature import canny
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

SRC = Path("assets/gate.png")  # 旧照片 512×512
W, H = 512, 512
EDGE = Path("assets/library_edges_old.png")
SEG = Path("assets/library_seg_old.png")


def main() -> None:
    img = Image.open(SRC).convert("RGB").resize((W, H), Image.LANCZOS)

    gray = rgb2gray(np.asarray(img))
    edges = canny(gray, sigma=2.0)
    Image.fromarray((edges * 255).astype(np.uint8)).save(EDGE)
    print("edges saved:", EDGE, "ratio=", round(float(edges.mean()), 4))

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
