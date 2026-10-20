"""把 10 张最终图排成 5 列 × 2 行，合成一张图（供论文插图）。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

EXP = Path("runs/exp_20261020_162214_d3ccf61b/runs")
OUT = Path("assets/library_10_grid.png")

CELL = 400
GAP = 14
LABEL_H = 30
COLS, ROWS = 5, 2


def main() -> None:
    imgs = []
    for i in range(1, 11):
        p = EXP / f"run_{i:03d}" / "final.png"
        im = Image.open(p).convert("RGB").resize((CELL, CELL), Image.LANCZOS)
        imgs.append((i, im))

    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()

    W = COLS * CELL + (COLS + 1) * GAP
    H = ROWS * (CELL + LABEL_H) + (ROWS + 1) * GAP
    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)

    for idx, (i, im) in enumerate(imgs):
        r = idx // COLS
        c = idx % COLS
        x = GAP + c * (CELL + GAP)
        y = GAP + r * (CELL + LABEL_H + GAP)
        canvas.paste(im, (x, y))
        draw.rectangle([x, y, x + CELL - 1, y + CELL - 1], outline="gray", width=2)
        label = str(i)
        tw = draw.textlength(label, font=font)
        draw.text((x + (CELL - tw) / 2, y + CELL + 4), label, fill="black", font=font)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT)
    print("saved", OUT, canvas.size)


if __name__ == "__main__":
    main()
