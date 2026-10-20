#!/usr/bin/env python3
"""生成一张原创、确定性的 Canny 控制图（标准边缘图格式：白线黑底）。

- 原创几何图形（天平 + 代码符号），避免任何第三方版权素材；
- 确定性绘制（无随机），可复现；
- 输出为「白线黑底」的标准 Canny 边缘图约定，可直接送入 Canny ControlNet，
  无需运行时再做边缘检测（更可复现、消除 opencv 版本依赖）；
- 输出到 assets/control_image.png，安装脚本会复制到 ComfyUI 的 input/ 目录。
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
WHITE = (255, 255, 255)


def main() -> int:
    img = Image.new("RGB", (SIZE, SIZE), "black")
    d = ImageDraw.Draw(img)

    # 底座与立柱
    d.rectangle([200, 420, 312, 440], fill=WHITE)
    d.rectangle([250, 200, 262, 420], fill=WHITE)
    # 横梁
    d.rectangle([120, 200, 392, 212], fill=WHITE)
    # 顶部圆点
    d.ellipse([244, 176, 268, 200], fill=WHITE)
    # 左右吊绳
    d.line([150, 200, 145, 240], fill=WHITE, width=5)
    d.line([362, 200, 367, 240], fill=WHITE, width=5)
    # 左右托盘（矩形框）
    d.rectangle([120, 240, 175, 300], outline=WHITE, width=6)
    d.rectangle([337, 240, 392, 300], outline=WHITE, width=6)
    # 左侧放一个实心方块（象征「权」）
    d.rectangle([135, 255, 160, 280], fill=WHITE)
    # 右侧放一个空心圆（象征「法」）
    d.ellipse([345, 255, 375, 285], outline=WHITE, width=6)
    # 代码符号：左右两个尖括号
    d.polygon([80, 110, 120, 140, 80, 170], outline=WHITE, width=6)
    d.polygon([432, 110, 392, 140, 432, 170], outline=WHITE, width=6)
    # 底部两条水平装饰线
    d.line([120, 380, 392, 380], fill=WHITE, width=4)
    d.line([160, 400, 352, 400], fill=WHITE, width=4)

    out = Path(__file__).resolve().parent.parent / "assets" / "control_image.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"已生成控制图（白线黑底边缘图）: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
