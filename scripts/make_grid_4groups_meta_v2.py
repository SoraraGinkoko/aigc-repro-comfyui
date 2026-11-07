"""方案 B（精简版）：2×2 元网格，无组标签，run 编号叠在每图左上角。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GROUPS = {
    (0, 0): "runs/exp_20261022_232653_fd42e4b9/runs",
    (0, 1): "runs/exp_20261022_234703_d8b72ab2/runs",
    (1, 0): "runs/exp_20261020_162214_d3ccf61b/runs",
    (1, 1): "runs/exp_20261022_171154_e2d5e477/runs",
}
OUT = "assets/ablation_meta_grid.png"

CELL = 140
GAP = 4
BLOCK_GAP_X = 20
BLOCK_GAP_Y = 14
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
        font_label = ImageFont.truetype("msyh.ttc", 14)
    except OSError:
        font_label = ImageFont.load_default()

    block_w = COLS * CELL + (COLS - 1) * GAP
    block_h = ROWS * CELL + (ROWS - 1) * GAP
    W = 2 * block_w + BLOCK_GAP_X
    H = 2 * block_h + BLOCK_GAP_Y
    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)

    for (r, c), exp in GROUPS.items():
        imgs = load_group(exp)
        bx = c * (block_w + BLOCK_GAP_X)
        by = r * (block_h + BLOCK_GAP_Y)
        for idx, im in enumerate(imgs):
            rr, cc = idx // COLS, idx % COLS
            x = bx + cc * (CELL + GAP)
            y = by + rr * (CELL + GAP)
            canvas.paste(im, (x, y))
            draw.rectangle([x, y, x + CELL - 1, y + CELL - 1], outline="#BBBBBB", width=1)
            # 左上角标签（深底白字）
            label = f"run_{idx+1:03d}"
            tw = draw.textlength(label, font=font_label)
            bw = int(tw) + 8
            bh = 18
            draw.rectangle([x, y, x + bw, y + bh], fill=(35, 35, 35))
            draw.text((x + 4, y + 1), label, fill="white", font=font_label)

    canvas.save(OUT)
    print("saved", OUT, canvas.size)


if __name__ == "__main__":
    main()
