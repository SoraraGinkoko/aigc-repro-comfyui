"""方案 B：2×2 元网格。行 = Canny（无/有），列 = Seg（无/有），每格为 5×2 的 10 张图。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# (row=Canny, col=Seg) -> (行标签, 列标签, 实验目录)
GROUPS = {
    (0, 0): ("无 Canny", "无 Seg", "runs/exp_20261022_232653_fd42e4b9/runs"),
    (0, 1): ("无 Canny", "有 Seg", "runs/exp_20261022_234703_d8b72ab2/runs"),
    (1, 0): ("有 Canny", "无 Seg", "runs/exp_20261020_162214_d3ccf61b/runs"),
    (1, 1): ("有 Canny", "有 Seg", "runs/exp_20261022_171154_e2d5e477/runs"),
}
OUT = "assets/ablation_meta_grid.png"

CELL = 150
GAP = 5
RUN_LABEL_H = 14
SIDE_W = 100
TOP_H = 44
BLOCK_GAP_X = 26
BLOCK_GAP_Y = 22
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
        font_side = ImageFont.truetype("msyh.ttc", 18)
        font_top = ImageFont.truetype("msyh.ttc", 18)
        font_run = ImageFont.truetype("msyh.ttc", 11)
    except OSError:
        font_side = font_top = font_run = ImageFont.load_default()

    block_w = COLS * CELL + (COLS - 1) * GAP
    block_h = ROWS * (CELL + RUN_LABEL_H) + (ROWS - 1) * GAP

    W = SIDE_W + BLOCK_GAP_X + 2 * block_w + BLOCK_GAP_X
    H = TOP_H + BLOCK_GAP_Y + 2 * block_h + BLOCK_GAP_Y
    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)

    for (r, c), (row_label, col_label, exp) in GROUPS.items():
        imgs = load_group(exp)
        bx = SIDE_W + BLOCK_GAP_X + c * (block_w + BLOCK_GAP_X)
        by = TOP_H + BLOCK_GAP_Y + r * (block_h + BLOCK_GAP_Y)

        # 列标签（顶部）
        if r == 0:
            tw = draw.textlength(col_label, font=font_top)
            draw.text((bx + block_w / 2 - tw / 2, 10), col_label, fill="black", font=font_top)
        # 行标签（左侧）
        if c == 0:
            tw = draw.textlength(row_label, font=font_side)
            draw.text((SIDE_W / 2 - tw / 2, by + block_h / 2 - 10), row_label,
                      fill="black", font=font_side)

        # 区块边框
        draw.rectangle([bx - 8, by - 8, bx + block_w + 8, by + block_h + 8],
                       outline="#CCCCCC", width=1)

        for idx, im in enumerate(imgs):
            rr, cc = idx // COLS, idx % COLS
            x = bx + cc * (CELL + GAP)
            y = by + rr * (CELL + RUN_LABEL_H + GAP)
            canvas.paste(im, (x, y))
            draw.rectangle([x, y, x + CELL - 1, y + CELL - 1], outline="#AAAAAA", width=1)
            label = f"run_{idx+1:03d}"
            tw = draw.textlength(label, font=font_run)
            draw.text((x + (CELL - tw) / 2, y + CELL + 1), label, fill="black", font=font_run)

    canvas.save(OUT)
    print("saved", OUT, canvas.size)


if __name__ == "__main__":
    main()
