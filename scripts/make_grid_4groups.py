"""四组消融结果总览：每组 10 张（5×2），四组纵向堆叠，左侧标注组合。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GROUPS = [
    ("无 Canny\n无 Seg", "runs/exp_20261022_232653_fd42e4b9/runs"),
    ("无 Canny\n有 Seg", "runs/exp_20261022_234703_d8b72ab2/runs"),
    ("有 Canny\n无 Seg", "runs/exp_20261020_162214_d3ccf61b/runs"),
    ("有 Canny\n有 Seg", "runs/exp_20261022_171154_e2d5e477/runs"),
]
OUT = "assets/ablation_4groups.png"

CELL = 210
GAP = 6
LABEL_H = 16
SIDE_W = 150
BLOCK_GAP = 22
COLS, ROWS = 5, 2


def load_group(exp: str):
    imgs = []
    for i in range(1, 11):
        p = Path(exp) / f"run_{i:03d}" / "final.png"
        im = Image.open(p).convert("RGB")
        im.thumbnail((CELL, CELL), Image.LANCZOS)
        canvas = Image.new("RGB", (CELL, CELL), "white")
        canvas.paste(im, ((CELL - im.width) // 2, (CELL - im.height) // 2))
        imgs.append(canvas)
    return imgs


def main() -> None:
    try:
        font_side = ImageFont.truetype("msyh.ttc", 20)
        font_run = ImageFont.truetype("msyh.ttc", 13)
    except OSError:
        font_side = ImageFont.load_default()
        font_run = ImageFont.load_default()

    block_w = COLS * CELL + (COLS - 1) * GAP
    block_h = ROWS * (CELL + LABEL_H) + (ROWS - 1) * GAP
    W = SIDE_W + GAP + block_w + GAP
    H = len(GROUPS) * (block_h + BLOCK_GAP) + GAP

    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)

    for bi, (label, exp) in enumerate(GROUPS):
        imgs = load_group(exp)
        y0 = GAP + bi * (block_h + BLOCK_GAP)
        # 左侧组合标签
        draw.multiline_text((GAP + 8, y0 + block_h / 2 - 20), label, fill="black",
                            font=font_side, spacing=4)
        # 分隔线
        if bi > 0:
            draw.line([(0, y0 - BLOCK_GAP / 2), (W, y0 - BLOCK_GAP / 2)], fill="#DDDDDD", width=1)
        for idx, im in enumerate(imgs):
            r, c = idx // COLS, idx % COLS
            x = SIDE_W + GAP + c * (CELL + GAP)
            y = y0 + r * (CELL + LABEL_H + GAP)
            canvas.paste(im, (x, y))
            draw.rectangle([x, y, x + CELL - 1, y + CELL - 1], outline="#AAAAAA", width=1)
            label2 = f"run_{idx+1:03d}"
            tw = draw.textlength(label2, font=font_run)
            draw.text((x + (CELL - tw) / 2, y + CELL + 2), label2, fill="black", font=font_run)

    canvas.save(OUT)
    print("saved", OUT, canvas.size)


if __name__ == "__main__":
    main()
