"""生成 assets/OpenHuman.ico —— 和页面 favicon 同一套视觉：近黑的壳 + 一个暖色点。

用法：<harness python> scripts/make_icon.py   （Pillow 只在工具链里有，项目 venv 不装）

为什么自己拼 ICO 而不是 `Image.save(format="ICO")`：Pillow 写出来的目录项里 `planes` 是 0，
而规范要求 1。.NET 容错，资源管理器不容错 —— 结果就是快捷方式显示成默认图标。
这里按 ICONDIR / ICONDIRENTRY / BITMAPINFOHEADER 手工拼：256 那帧用 PNG（Vista 起支持），
小尺寸用 32bpp BMP（兼容性最好）。
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "OpenHuman.ico"

BG = (10, 12, 15, 255)          # #0a0c0f
WARM = (217, 180, 135, 255)     # #d9b487
HAIR = (236, 230, 220, 46)      # 边框：冷壳在深色任务栏上得看得见

SIZES = (16, 24, 32, 48, 64, 128, 256)
SS = 8  # 超采样倍数，圆角和圆点才不毛边


def draw(size: int) -> Image.Image:
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = round(big * 0.02)
    radius = big * 0.22
    d.rounded_rectangle(
        (pad, pad, big - pad - 1, big - pad - 1),
        radius=radius,
        fill=BG,
        outline=HAIR,
        width=max(1, big // 64),
    )

    # 暖点：favicon 里是 32 格里的 r=4.5，这里按同样比例
    r = big * 0.141
    cx = cy = big / 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=WARM)

    return img.resize((size, size), Image.LANCZOS)


def as_bmp(img: Image.Image) -> bytes:
    """32bpp DIB（不带文件头的 BMP）+ 1bpp AND 掩码。资源管理器最吃的就是这个。"""
    w, h = img.size
    pixels = img.load()

    xor = bytearray()
    for y in range(h - 1, -1, -1):  # BMP 自下而上
        for x in range(w):
            r, g, b, a = pixels[x, y]
            xor += bytes((b, g, r, a))

    stride = ((w + 31) // 32) * 4  # 1bpp，行按 4 字节对齐
    and_mask = bytearray(stride * h)  # 全 0 = 不透明；透明交给 alpha 通道

    header = struct.pack(
        "<IiiHHIIiiII",
        40,                       # biSize
        w,                        # biWidth
        h * 2,                    # biHeight：XOR 位图 + AND 掩码
        1,                        # biPlanes —— 必须是 1
        32,                       # biBitCount
        0,                        # BI_RGB
        len(xor) + len(and_mask),  # biSizeImage
        0, 0, 0, 0,
    )
    return header + bytes(xor) + bytes(and_mask)


def as_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def build(frames: list[Image.Image]) -> bytes:
    blobs = [as_png(f) if f.size[0] >= 256 else as_bmp(f) for f in frames]

    out = bytearray(struct.pack("<HHH", 0, 1, len(frames)))  # ICONDIR
    offset = 6 + 16 * len(frames)
    for frame, blob in zip(frames, blobs):
        w, h = frame.size
        out += struct.pack(
            "<BBBBHHII",
            w if w < 256 else 0,   # 256 写成 0
            h if h < 256 else 0,
            0,                     # 调色板色数
            0,                     # 保留
            1,                     # planes —— 规范要求 1
            32,                    # 位深
            len(blob),
            offset,
        )
        offset += len(blob)
    for blob in blobs:
        out += blob
    return bytes(out)


def verify(path: Path) -> None:
    raw = path.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", raw[:6])
    assert (reserved, kind) == (0, 1), "不是 ICO"
    assert count == len(SIZES), f"目录项 {count} 个，应为 {len(SIZES)}"
    for i in range(count):
        w, h, _c, _r, planes, bpp, size, offset = struct.unpack(
            "<BBBBHHII", raw[6 + 16 * i : 22 + 16 * i]
        )
        assert planes == 1, f"第 {i} 项 planes={planes}，必须是 1"
        assert bpp == 32, f"第 {i} 项 bpp={bpp}"
        assert offset + size <= len(raw), f"第 {i} 项越界"
    print(f"verified: {count} 项，planes=1 / bpp=32，{len(raw)} bytes")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(build([draw(s) for s in SIZES]))
    verify(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
